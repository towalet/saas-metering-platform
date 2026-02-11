from typing import Literal

from pydantic import BaseModel, Field, EmailStr

# Input schema for creating an org
class OrgCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)

# Output schema for an org
class OrgOut(BaseModel):
    id: int
    name: str
    # of members in the org
    class Config:
        from_attributes = True

# Input schema for adding a member to an org
class OrgMemberAddIn(BaseModel):
    email: EmailStr
    role: Literal["owner", "admin", "member"] = "member"

# Output schema for an org member
class OrgMemberOut(BaseModel):
    user_id: int
    email: EmailStr
    role: str
