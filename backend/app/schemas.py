from pydantic import BaseModel, EmailStr
class AuthIn(BaseModel): email: EmailStr; password: str
class QueryIn(BaseModel): question: str
class MetadataIn(BaseModel):
    title:str|None=None; source:str="User upload"; authority:float=50; version:str="unversioned"; createdDate:str|None=None; effectiveDate:str|None=None; expiryDate:str|None=None
