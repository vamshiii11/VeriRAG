export const API_TOKEN_KEY="verirag-token";
const pendingGets = new Map<string, Promise<Response>>();
export function token(){return localStorage.getItem(API_TOKEN_KEY)||"";}
function handleUnauthorized(response:Response,requestToken:string){
	if(response.status===401&&requestToken&&token()===requestToken){
		localStorage.removeItem(API_TOKEN_KEY);
		window.dispatchEvent(new Event("verirag:unauthorized"));
	}
	return response;
}
export async function apiFetch(input:RequestInfo|URL,init:RequestInit={}){
	const headers=new Headers(input instanceof Request ? input.headers : undefined);
	new Headers(init.headers).forEach((value,key)=>headers.set(key,value));
	const authToken=token();
	if(authToken) headers.set("Authorization",`Bearer ${authToken}`);
	const method=(init.method||(input instanceof Request ? input.method : "GET")).toUpperCase();
	const request={...init,headers};
	if(method!=="GET"||init.signal) return handleUnauthorized(await fetch(input,request),authToken);
	const url=input instanceof Request ? input.url : input.toString();
	const key=`${authToken}:${url}`;
	const existing=pendingGets.get(key);
	if(existing) return handleUnauthorized((await existing).clone(),authToken);
	const pending=fetch(input,request);
	pendingGets.set(key,pending);
	try{return handleUnauthorized((await pending).clone(),authToken);}
	finally{if(pendingGets.get(key)===pending) pendingGets.delete(key);}
}
