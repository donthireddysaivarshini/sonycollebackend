from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Automated health check endpoint.
    Returns status 200 OK with service operational metrics.
    """
    return Response(
        {
            "status": "healthy",
            "service": "sony-feeding-kurtis-backend",
            "version": "1.0.0",
            "environment": "development",
        },
        status=status.HTTP_200_OK,
    )

