class ASSTError(Exception):
    """助手"""
    def __init__(self, message, return_msg):
        super().__init__(message)
        self.return_msg = return_msg

