
from .deploy import MaxKBDeployer
from .api_client import MaxKBClient

# 检查哪些客户端类可用
try:
    from .jwt_client_fixed import MaxKBFixedClient
    __all__ = ['MaxKBDeployer', 'MaxKBClient', 'MaxKBFixedClient']
except ImportError:
    try:
        from .jwt_client import MaxKBJWTClient
        __all__ = ['MaxKBDeployer', 'MaxKBClient', 'MaxKBJWTClient']
    except ImportError:
        __all__ = ['MaxKBDeployer', 'MaxKBClient']