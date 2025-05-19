# Planty Server

This is the FastAPI server for the Planty project, providing authentication endpoints for the Android application.

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

To run the server in development mode:
```bash
python main.py
```

The server will start at `http://localhost:8000`

## API Endpoints

### Authentication

#### Login
- **POST** `/auth/login`
- Request body:
```json
{
    "userId": "string",
    "userPw": "string"
}
```

#### Signup
- **POST** `/auth/signup`
- Request body:
```json
{
    "nickname": "string",
    "userId": "string",
    "userPw": "string",
    "email": "string"
}
```

## Security Note

Before deploying to production:
1. Change the `SECRET_KEY` in `main.py`
2. Implement proper database storage instead of the mock database
3. Add proper error handling and logging
4. Configure CORS settings
5. Add rate limiting
6. Use HTTPS in production 