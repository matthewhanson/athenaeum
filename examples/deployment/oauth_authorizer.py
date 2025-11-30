"""
Lambda authorizer for OAuth/JWT authentication.
Validates JWT tokens from Authorization header.
"""
import os
import json
from typing import Dict, Any
from jose import jwt, jwk
from jose.exceptions import JWTError
import requests


def get_jwks():
    """Fetch JWKS from OAuth provider."""
    jwks_url = os.environ.get("OAUTH_JWKS_URL")
    if not jwks_url:
        raise ValueError("OAUTH_JWKS_URL not configured")
    
    response = requests.get(jwks_url)
    response.raise_for_status()
    return response.json()


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return claims.
    
    Args:
        token: JWT token string
        
    Returns:
        Dict of token claims
        
    Raises:
        JWTError: If token is invalid
    """
    issuer = os.environ.get("OAUTH_ISSUER")
    audience = os.environ.get("OAUTH_AUDIENCE")
    
    if not issuer or not audience:
        raise ValueError("OAuth configuration missing")
    
    # Get JWKS and verify token
    jwks = get_jwks()
    
    # Decode token header to get key ID
    unverified_header = jwt.get_unverified_header(token)
    key_id = unverified_header.get("kid")
    
    # Find matching key in JWKS
    key = None
    for jwk_key in jwks.get("keys", []):
        if jwk_key.get("kid") == key_id:
            key = jwk_key
            break
    
    if not key:
        raise JWTError("Public key not found in JWKS")
    
    # Verify and decode token
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
    )
    
    return claims


def generate_policy(principal_id: str, effect: str, resource: str, context: Dict = None) -> Dict:
    """
    Generate IAM policy for API Gateway.
    
    Args:
        principal_id: User identifier
        effect: "Allow" or "Deny"
        resource: API Gateway resource ARN
        context: Additional context to pass to Lambda
        
    Returns:
        IAM policy document
    """
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
        "context": context or {},
    }


def handler(event: Dict[str, Any], context: Any) -> Dict:
    """
    Lambda authorizer handler.
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context
        
    Returns:
        IAM policy allowing or denying access
    """
    try:
        # Extract token from Authorization header
        auth_header = event.get("headers", {}).get("Authorization", "")
        
        if not auth_header:
            raise ValueError("Authorization header missing")
        
        # Remove "Bearer " prefix
        token = auth_header.replace("Bearer ", "").strip()
        
        if not token:
            raise ValueError("Token missing")
        
        # Verify token
        claims = verify_token(token)
        
        # Extract user info
        principal_id = claims.get("sub", "unknown")
        email = claims.get("email")
        
        # Generate allow policy
        policy = generate_policy(
            principal_id=principal_id,
            effect="Allow",
            resource=event["methodArn"],
            context={
                "email": email or "",
                "userId": principal_id,
            },
        )
        
        return policy
        
    except Exception as e:
        print(f"Authorization failed: {e}")
        # Return deny policy
        return generate_policy(
            principal_id="unauthorized",
            effect="Deny",
            resource=event["methodArn"],
        )
