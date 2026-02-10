from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.auth import SignupIn, LoginIn, TokenOut, UserOut
from app.services.users import get_user_by_email, create_user
from app.core.security import verify_password, create_access_token, decode_token
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# signup endpoint
@router.post("/signup", response_model = UserOut, status_code = 201)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    # Check if user with the same email already exists
    existing_user = get_user_by_email(db, email=payload.email)
    # If user exists, raise an HTTPException with a 400 status code and a message indicating that the email is already registered
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    # If user does not exist, create a new user using the create_user function and return the created user
    user = create_user(db, email=payload.email, password=payload.password)
    return user

# login endpoint
@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    # Retrieve the user from the database using the provided email
    user = get_user_by_email(db, email=payload.email)
    # If the user does not exist or the password is incorrect, raise an HTTPException with a 401 status code and a message indicating invalid credentials
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # If the credentials are valid, create an access token using the create_access_token function and return it in a TokenOut response model
    access_token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=access_token)

def getCurrentUser(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        # Decode the token to get the user ID
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    # Retrieve the user from the database using the user ID
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(getCurrentUser)):
    return current_user
