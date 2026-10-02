import {
  ChangeEvent,
  DragEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { apiFetch } from "@/lib/api";
import {
  ArrowDownToLine,
  Check,
  ChevronDown,
  Clock3,
  File,
  FileText,
  Filter,
  MoreHorizontal,
  Search,
  Trash2,
  UploadCloud,
  X,
  Zap,
} from "lucide-react";

type DocumentStatus =
  | "Indexed"
  | "Processing"
  | "Needs review"
  | "Failed";

type WorkspaceDocument = {
  id: string;
  name: string;
  type: string;
  size: string;
  pages: number;
  updated: string;
  status: DocumentStatus;
  chunks: number;
  source: string;
};

const statusStyles: Record<DocumentStatus, string> = {
  Indexed: "bg-[#edf9f4] text-[#45ae91]",
  Processing: "bg-[#eff8d0] text-[#758c2a]",
  "Needs review": "bg-[#fff5e8] text-[#c18432]",
  Failed: "bg-[#fff0f0] text-[#cc6565]",
};

function formatSize(size: number) {
  if (!size || size <= 0) {
    return "0 KB";
  }

  if (size > 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(size / 1024))} KB`;
}

function mapStatus(status: string): DocumentStatus {
  switch (status) {
    case "INDEXED":
      return "Indexed";

    case "PROCESSING":
      return "Processing";

    case "FAILED":
      return "Failed";

    default:
      return "Needs review";
  }
}

function mapDocument(record: any): WorkspaceDocument {
  const filename =
    record.filename ||
    record.original_filename ||
    "Unnamed document";

  return {
    id: String(record.id),
    name: filename,
    type:
      filename.split(".").pop()?.toUpperCase() ||
      "FILE",
    size: formatSize(Number(record.size || record.file_size || 0)),
    pages: Number(record.pages || 0),
    updated: record.createdAt
      ? new Date(record.createdAt).toLocaleDateString()
      : record.created_at
        ? new Date(record.created_at).toLocaleDateString()
        : "Recently",
    status: mapStatus(record.status),
    chunks: Number(record.chunks || 0),
    source: record.source || "User upload",
  };
}

async function readApiError(response: Response) {
  const contentType =
    response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const body = await response.json();

      return (
        body?.detail ||
        body?.message ||
        body?.error ||
        `Request failed with status ${response.status}`
      );
    } catch {
      return `Request failed with status ${response.status}`;
    }
  }

  try {
    const text = await response.text();

    if (text.trim()) {
      return `Server returned ${response.status}: ${text
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 200)}`;
    }
  } catch {
    // Ignore response parsing failure.
  }

  return `Request failed with status ${response.status}`;
}

export default function Documents() {
  const [documents, setDocuments] = useState<
    WorkspaceDocument[]
  >([]);

  const [loading, setLoading] = useState(true);

  const [query, setQuery] = useState("");

  const [filter, setFilter] = useState<
    "All" | DocumentStatus
  >("All");

  const [isDragging, setIsDragging] = useState(false);

  const [showUpload, setShowUpload] = useState(false);

  const [selectedDocument, setSelectedDocument] =
    useState<WorkspaceDocument | null>(null);

  const [uploadError, setUploadError] = useState("");

  const [uploading, setUploading] = useState(false);

  const [metadata, setMetadata] = useState({
    title: "",
    source: "User upload",
    authority: "50",
    version: "",
    effectiveDate: "",
    expiryDate: "",
  });

  const inputRef = useRef<HTMLInputElement>(null);

  /*
   * Load documents from the Render backend.
   */
  const loadDocuments = async () => {
    setLoading(true);

    try {
      const response = await apiFetch("/api/documents");

      if (!response.ok) {
        throw new Error(
          await readApiError(response),
        );
      }

      const contentType =
        response.headers.get("content-type") || "";

      if (!contentType.includes("application/json")) {
        throw new Error(
          "The backend returned an invalid response.",
        );
      }

      const records = await response.json();

      if (!Array.isArray(records)) {
        throw new Error(
          "The documents API returned an invalid format.",
        );
      }

      setDocuments(records.map(mapDocument));
    } catch (error) {
      console.error(
        "Failed to load documents:",
        error,
      );

      setDocuments([]);

      setUploadError(
        error instanceof Error
          ? error.message
          : "Could not load documents from the backend.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDocuments();
  }, []);

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesFilter =
        filter === "All" ||
        doc.status === filter;

      const matchesSearch =
        doc.name
          .toLowerCase()
          .includes(query.toLowerCase());

      return matchesFilter && matchesSearch;
    });
  }, [documents, filter, query]);

  const indexedCount = documents.filter(
    (doc) => doc.status === "Indexed",
  ).length;

  const totalChunks = documents.reduce(
    (sum, doc) => sum + doc.chunks,
    0,
  );

  /*
   * Upload selected files.
   */
  const addFiles = async (
    files: FileList | File[],
  ) => {
    const accepted = Array.from(files).filter(
      (file) =>
        /\.(pdf|docx?|txt|png|jpe?g)$/i.test(
          file.name,
        ),
    );

    if (!accepted.length) {
      setUploadError(
        "Please select a PDF, DOC, DOCX, TXT, PNG, JPG or JPEG file.",
      );
      return;
    }

    setUploadError("");
    setUploading(true);

    try {
      const uploadedRecords: any[] = [];
      const errors: string[] = [];

      for (const file of accepted) {
        try {
          if (
            file.size >
            25 * 1024 * 1024
          ) {
            throw new Error(
              `${file.name}: file exceeds the 25 MB limit.`,
            );
          }

          const form = new FormData();

          form.append("file", file);

          form.append(
            "metadata_json",
            JSON.stringify({
              title:
                metadata.title.trim() ||
                file.name,

              source:
                metadata.source.trim() ||
                "User upload",

              authority:
                Number(metadata.authority) || 0,

              version:
                metadata.version.trim() ||
                "unversioned",

              effectiveDate:
                metadata.effectiveDate ||
                null,

              expiryDate:
                metadata.expiryDate ||
                null,
            }),
          );

          /*
           * IMPORTANT:
           * Do not manually set Content-Type here.
           * The browser automatically creates the
           * multipart/form-data boundary.
           */
          const response = await apiFetch(
            "/api/documents",
            {
              method: "POST",
              body: form,
            },
          );

          if (!response.ok) {
            throw new Error(
              await readApiError(response),
            );
          }

          const contentType =
            response.headers.get(
              "content-type",
            ) || "";

          if (
            !contentType.includes(
              "application/json",
            )
          ) {
            throw new Error(
              "Upload succeeded but the backend returned an invalid response.",
            );
          }

          const record =
            await response.json();

          uploadedRecords.push(record);
        } catch (error) {
          console.error(
            `Upload failed for ${file.name}:`,
            error,
          );

          errors.push(
            error instanceof Error
              ? error.message
              : `${file.name}: upload failed.`,
          );
        }
      }

      /*
       * Add successful uploads immediately.
       */
      if (uploadedRecords.length) {
        const mapped =
          uploadedRecords.map(mapDocument);

        setDocuments((current) => [
          ...mapped,
          ...current.filter(
            (existing) =>
              !mapped.some(
                (item) =>
                  item.id === existing.id,
              ),
          ),
        ]);
      }

      /*
       * Display failures clearly.
       */
      if (errors.length) {
        setUploadError(
          errors.join(" | "),
        );
      } else if (uploadedRecords.length) {
        setUploadError("");
        setShowUpload(false);
      }

      /*
       * Refresh from backend so the UI represents
       * the actual database state.
       */
      if (uploadedRecords.length) {
        await loadDocuments();
      }
    } finally {
      setUploading(false);
    }
  };

  const handleInput = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    if (event.target.files) {
      void addFiles(event.target.files);
    }

    event.target.value = "";
  };

  const handleDrop = (
    event: DragEvent<HTMLDivElement>,
  ) => {
    event.preventDefault();

    setIsDragging(false);

    void addFiles(
      event.dataTransfer.files,
    );
  };

  /*
   * Delete document.
   */
  const removeDocument = async (
    id: string,
  ) => {
    const target = documents.find(
      (doc) => doc.id === id,
    );

    if (
      !window.confirm(
        `Delete ${
          target?.name ||
          "this document"
        }? This cannot be undone.`,
      )
    ) {
      return;
    }

    try {
      const response = await apiFetch(
        `/api/documents/${id}`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error(
          await readApiError(response),
        );
      }

      setDocuments((current) =>
        current.filter(
          (doc) => doc.id !== id,
        ),
      );

      if (
        selectedDocument?.id === id
      ) {
        setSelectedDocument(null);
      }
    } catch (error) {
      setUploadError(
        error instanceof Error
          ? error.message
          : "Could not delete the document.",
      );
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg"
        className="hidden"
        onChange={handleInput}
      />

      {/* Header */}
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.15em] text-[#8491a3]">
            <FileText className="h-3.5 w-3.5 text-[#b4a4ff]" />
            Knowledge base
          </div>

          <h1 className="font-display text-3xl font-semibold tracking-[-0.045em] text-[#172333] sm:text-[40px]">
            Documents
            <span className="text-[#d6e887]">
              .
            </span>
          </h1>

          <p className="mt-2 text-sm text-[#718096]">
            Upload and manage the evidence that
            powers every VeriRAG answer.
          </p>
        </div>

        <button
          onClick={() => {
            setUploadError("");
            setShowUpload(true);
          }}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#101827] px-5 text-xs font-semibold text-white shadow-[0_8px_24px_rgba(16,24,39,.14)] transition hover:-translate-y-0.5 hover:bg-[#1a2b40]"
        >
          <UploadCloud className="h-4 w-4 text-[#d8f76c]" />
          Add documents
        </button>
      </div>

      {/* Stats */}
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-[#e3e8f0] bg-white p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#94a0af]">
            Total documents
          </p>

          <p className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em]">
            {documents.length}
          </p>

          <p className="mt-1 text-[11px] text-[#8e9baa]">
            Across your workspace
          </p>
        </div>

        <div className="rounded-2xl border border-[#e3e8f0] bg-white p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#94a0af]">
            Indexed and ready
          </p>

          <p className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em]">
            {indexedCount}
          </p>

          <p className="mt-1 flex items-center gap-1 text-[11px] text-[#45ae91]">
            <Check className="h-3 w-3" />
            Available for retrieval
          </p>
        </div>

        <div className="rounded-2xl border border-[#e3e8f0] bg-white p-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#94a0af]">
            Evidence chunks
          </p>

          <p className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em]">
            {totalChunks}
          </p>

          <p className="mt-1 text-[11px] text-[#8e9baa]">
            Embedded and searchable
          </p>
        </div>
      </div>

      {/* Error */}
      {uploadError && (
        <div className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-[#f2caca] bg-[#fff5f5] px-4 py-3 text-xs text-[#b25c63]">
          <span className="break-words">
            {uploadError}
          </span>

          <button
            onClick={() =>
              setUploadError("")
            }
            className="shrink-0"
            aria-label="Close error"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {loading && (
        <p className="mt-5 text-xs text-[#8491a3]">
          Loading documents...
        </p>
      )}

      {/* Upload area */}
      {showUpload && (
        <div
          onDragEnter={() =>
            setIsDragging(true)
          }
          onDragOver={(event) =>
            event.preventDefault()
          }
          onDragLeave={() =>
            setIsDragging(false)
          }
          onDrop={handleDrop}
          className={`mt-5 rounded-2xl border-2 border-dashed p-8 text-center transition ${
            isDragging
              ? "border-[#a8c151] bg-[#f4fad9]"
              : "border-[#cfd8e4] bg-white"
          }`}
        >
          <button
            onClick={() =>
              setShowUpload(false)
            }
            className="float-right text-[#9da8b6] hover:text-[#172333]"
            aria-label="Close upload"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eff8d0] text-[#718c27]">
            <UploadCloud className="h-5 w-5" />
          </div>

          <h3 className="mt-4 text-sm font-semibold text-[#273447]">
            Drop documents here
          </h3>

          <p className="mt-1 text-xs text-[#8491a3]">
            PDF, DOCX, TXT, or scanned images up
            to 25 MB each
          </p>

          <div className="mx-auto mt-5 grid max-w-2xl gap-2 text-left sm:grid-cols-2">
            <input
              value={metadata.title}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  title: event.target.value,
                })
              }
              placeholder="Title (optional)"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />

            <input
              value={metadata.source}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  source: event.target.value,
                })
              }
              placeholder="Source"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />

            <input
              value={metadata.version}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  version: event.target.value,
                })
              }
              placeholder="Version (optional)"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />

            <input
              value={metadata.authority}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  authority: event.target.value,
                })
              }
              type="number"
              min="0"
              max="100"
              placeholder="Authority 0-100"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />

            <input
              value={metadata.effectiveDate}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  effectiveDate:
                    event.target.value,
                })
              }
              type="date"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />

            <input
              value={metadata.expiryDate}
              onChange={(event) =>
                setMetadata({
                  ...metadata,
                  expiryDate:
                    event.target.value,
                })
              }
              type="date"
              className="h-9 rounded-lg border border-[#e3e8f0] px-3 text-xs"
            />
          </div>

          <button
            disabled={uploading}
            onClick={() =>
              inputRef.current?.click()
            }
            className="mt-5 rounded-lg bg-[#101827] px-4 py-2.5 text-[11px] font-semibold text-white transition hover:bg-[#1b2a3f] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading
              ? "Uploading..."
              : "Browse files"}
          </button>

          <p className="mt-3 text-[10px] text-[#a3aebb]">
            Files are processed by the VeriRAG API
          </p>
        </div>
      )}

      {/* Documents table */}
      <div className="mt-7 rounded-2xl border border-[#e3e8f0] bg-white">
        <div className="flex flex-col justify-between gap-4 border-b border-[#edf0f4] p-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-display text-lg font-semibold tracking-[-0.025em]">
              Your documents
            </h2>

            <p className="mt-1 text-xs text-[#8491a3]">
              Every file is extracted, chunked, and
              indexed for evidence retrieval.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9aa6b5]" />

              <input
                value={query}
                onChange={(event) =>
                  setQuery(event.target.value)
                }
                className="h-9 w-full rounded-lg border border-[#e3e8f0] bg-[#fbfcfe] pl-9 pr-3 text-[11px] outline-none focus:border-[#b7c78b] sm:w-52"
                placeholder="Search documents"
              />
            </div>

            <div className="relative">
              <Filter className="pointer-events-none absolute left-3 top-1/2 h-3 w-3 -translate-y-1/2 text-[#9aa6b5]" />

              <select
                value={filter}
                onChange={(event) =>
                  setFilter(
                    event.target.value as
                      | "All"
                      | DocumentStatus,
                  )
                }
                className="h-9 appearance-none rounded-lg border border-[#e3e8f0] bg-[#fbfcfe] pl-8 pr-8 text-[11px] text-[#607084] outline-none focus:border-[#b7c78b]"
              >
                <option>All</option>
                <option>Indexed</option>
                <option>Processing</option>
                <option>Needs review</option>
                <option>Failed</option>
              </select>

              <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-[#9aa6b5]" />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <thead>
              <tr className="border-b border-[#edf0f4] text-[10px] font-semibold uppercase tracking-[0.12em] text-[#9ba7b5]">
                <th className="px-5 py-3 font-semibold">
                  Document
                </th>

                <th className="px-4 py-3 font-semibold">
                  Source
                </th>

                <th className="px-4 py-3 font-semibold">
                  Status
                </th>

                <th className="px-4 py-3 font-semibold">
                  Chunks
                </th>

                <th className="px-4 py-3 font-semibold">
                  Updated
                </th>

                <th className="px-5 py-3 text-right font-semibold">
                  Actions
                </th>
              </tr>
            </thead>

            <tbody>
              {filteredDocuments.map(
                (doc) => (
                  <tr
                    key={doc.id}
                    className="group border-b border-[#f0f2f5] last:border-0 hover:bg-[#fbfcfe]"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                            doc.type === "PDF"
                              ? "bg-[#fff0f0] text-[#d87373]"
                              : "bg-[#edf2ff] text-[#7187dc]"
                          }`}
                        >
                          <File className="h-4 w-4" />
                        </div>

                        <div>
                          <p className="text-xs font-semibold text-[#344154]">
                            {doc.name}
                          </p>

                          <p className="mt-1 text-[10px] text-[#9aa6b5]">
                            {doc.type} ·{" "}
                            {doc.size}
                            {doc.pages
                              ? ` · ${doc.pages} pages`
                              : ""}
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-4 text-[11px] text-[#718096]">
                      {doc.source}
                    </td>

                    <td className="px-4 py-4">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[9px] font-bold ${statusStyles[doc.status]}`}
                      >
                        {doc.status ===
                          "Processing" && (
                          <Clock3 className="h-3 w-3 animate-spin" />
                        )}

                        {doc.status ===
                          "Indexed" && (
                          <Check className="h-3 w-3" />
                        )}

                        {doc.status}
                      </span>
                    </td>

                    <td className="px-4 py-4 text-[11px] font-semibold text-[#59677a]">
                      {doc.chunks || "—"}
                    </td>

                    <td className="px-4 py-4 text-[11px] text-[#8794a5]">
                      {doc.updated}
                    </td>

                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={() =>
                          setSelectedDocument(
                            doc,
                          )
                        }
                        className="rounded-lg p-2 text-[#a6b0bd] transition hover:bg-[#f0f3f7] hover:text-[#273447]"
                        aria-label={`View ${doc.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>

                      <button
                        onClick={() =>
                          void removeDocument(
                            doc.id,
                          )
                        }
                        className="ml-1 rounded-lg p-2 text-[#a6b0bd] transition hover:bg-[#fff0f0] hover:text-[#cc6565]"
                        aria-label={`Delete ${doc.name}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>

          {filteredDocuments.length === 0 &&
            !loading && (
              <div className="px-6 py-16 text-center">
                <Search className="mx-auto h-6 w-6 text-[#b1bcc8]" />

                <p className="mt-3 text-sm font-semibold text-[#526074]">
                  No documents found
                </p>

                <p className="mt-1 text-xs text-[#95a0ae]">
                  Try another search or upload a
                  new file.
                </p>
              </div>
            )}
        </div>
      </div>

      {/* Document details */}
      {selectedDocument && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#101827]/45 p-5"
          onClick={() =>
            setSelectedDocument(null)
          }
        >
          <div
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold">
                {selectedDocument.name}
              </h2>

              <button
                onClick={() =>
                  setSelectedDocument(null)
                }
                aria-label="Close document details"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl bg-[#f7f9fb] p-3">
                <p className="text-[#9aa6b5]">
                  Status
                </p>

                <p className="mt-1 font-semibold">
                  {selectedDocument.status}
                </p>
              </div>

              <div className="rounded-xl bg-[#f7f9fb] p-3">
                <p className="text-[#9aa6b5]">
                  Chunks
                </p>

                <p className="mt-1 font-semibold">
                  {selectedDocument.chunks}
                </p>
              </div>

              <div className="rounded-xl bg-[#f7f9fb] p-3">
                <p className="text-[#9aa6b5]">
                  Source
                </p>

                <p className="mt-1 font-semibold">
                  {selectedDocument.source}
                </p>
              </div>

              <div className="rounded-xl bg-[#f7f9fb] p-3">
                <p className="text-[#9aa6b5]">
                  Size
                </p>

                <p className="mt-1 font-semibold">
                  {selectedDocument.size}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bottom information */}
      <div className="mt-5 flex items-center gap-3 rounded-2xl border border-dashed border-[#cfd8e4] bg-[#fbfcfe] p-4">
        <Zap className="h-4 w-4 shrink-0 text-[#b5c95b]" />

        <p className="text-[11px] leading-5 text-[#758397]">
          Supported files are automatically
          prepared for hybrid retrieval. Once
          indexed, every chunk keeps its source,
          page, version, and authority metadata.
        </p>
      </div>
    </div>
  );
}