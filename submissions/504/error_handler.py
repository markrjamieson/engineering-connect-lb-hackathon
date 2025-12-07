"""
Error Handler module.
Handles error responses with appropriate status codes.
"""
from flask import Response


def handle_error(status_code: int, message: str = '') -> Response:
    """
    Create an error response with the given status code.
    
    Args:
        status_code: HTTP status code (404, 502, 503, 504)
        message: Optional error message (not returned to client, empty payload per requirements)
        
    Returns:
        Flask Response with appropriate status code and empty payload
    """
    return Response('', status=status_code)

