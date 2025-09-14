from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import exceptions
import jwt
from django.conf import settings

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        print("🔍 Authentication check in CookieJWTAuthentication")
        
        raw_token = request.COOKIES.get('token')
        print("🔍 Raw token exists:", bool(raw_token))
        if raw_token:
            print("🔍 Raw token (first 50 chars):", raw_token[:50])
        
        if raw_token is None:
            print("❌ No token found in cookies")
            return None
            
        try:
            print("🔍 Attempting to decode JWT...")
            print("🔍 Using secret:", settings.JWT_SECRET[:10] + "..." if settings.JWT_SECRET else "NOT SET")
            
            # Decode JWT using the same secret as Node.js
            payload = jwt.decode(
                raw_token, 
                settings.JWT_SECRET,
                algorithms=["HS256"]
            )
            
            print("✅ JWT Payload decoded successfully:", payload)
            
            # Your JWT structure: {id: user.id, iat: ..., exp: ...}
            user_id = payload.get('id')
            if not user_id:
                print("❌ No user ID in token payload")
                return None
            
            print(f"✅ Found user ID in token: {user_id}")
            
            # Create a mock user object for Django DRF
            class AuthenticatedUser:
                def __init__(self, user_id):
                    self.id = user_id
                    self.is_authenticated = True
                    
                def __str__(self):
                    return f"User(id={self.id})"
            
            user = AuthenticatedUser(user_id)
            print("✅ User authenticated with ID:", user_id)
            return (user, raw_token)
            
        except jwt.ExpiredSignatureError:
            print("❌ Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"❌ Invalid token: {e}")
            return None
        except jwt.DecodeError as e: # type: ignore
            print(f"❌ JWT decode error: {e}")
            return None
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            import traceback
            traceback.print_exc()
            return None