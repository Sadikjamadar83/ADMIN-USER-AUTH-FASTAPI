
from fastapi import FastAPI,Depends,HTTPException,status

from sqlalchemy.orm import Session

import models, schemas, utils
from database import engine,get_db
import jose
from jose import JWTError, jwt

from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm,OAuth2PasswordBearer
from jose import JWTError


SECRET_KEY = "e44af21dc7c63b34665c85c8a86c3ecdc2116e7277deeeda5fca9c2663165b62"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

#Helper function that takes user data 

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encode_jwt

from database import engine, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(debug=True)

@app.post("/signup")
def  register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if the user already exists
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    # Hash the password
    hashed_password = utils.hash_password(user.password)

    # Create a new user instance
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role 
    )

    # Add the new user to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return { "message": "User registered successfully",'id': new_user.id, "username": new_user.username, "email": new_user.email, "role": new_user.role}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user :
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username")

    if not utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token_data = {"sub": user.username, "role": user.role}
    token = create_access_token(token_data)
    return {"access_token": token, "token_type": "bearer", "role": user.role}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token:str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return {"username": username, "role": role}

@app.get("/protected")
def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {current_user['username']}! You have access to this protected route.", "role": current_user['role']}

def require_roles(allowed_roles: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access this resource.")
        return current_user
    return role_checker

@app.get("/profile")
def profile(current_user : dict = Depends(require_roles(["user","admin"]))):
    return {"message": f"Hello, {current_user['username']}! This is your profile.", "role": current_user['role']}

@app.get("/user/dashboard")
def user_dashboard(current_user: dict = Depends(require_roles("user"))):
    return {"message":"Welcome User"}

@app.get("/admin/dashboard")
def admin_dashboard(current_user: dict = Depends(require_roles("admin"))):
    return {"message":"Welcome Admin"}