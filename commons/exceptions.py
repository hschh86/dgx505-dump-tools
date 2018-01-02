# Basic exceptions
class ExtractorError(Exception):
    """Base class for custom exceptions"""
    pass


class MalformedDataError(ExtractorError):
    """
    Exception to be raised when something unexpected happens while
    parsing the data extracted from the messages
    """
    pass


class NotRecordedError(ExtractorError):
    """
    Exception to be raised when trying to get something that wasn't recorded
    """
    pass


# message errors
class MessageError(ExtractorError):
    def __init__(self, description, msg=None):
        self.description = description
        self.msg = msg


class MessageParsingError(MessageError):
    """
    Exception raised when something unexpected happens while parsing messages
    """
    pass


class MessageSequenceError(MessageError):
    """
    Exception raised on errors while collecting a sequence of messages
    """
    def __init__(self, description, dmsg=None):
        self.dmsg = dmsg
        if dmsg is None:
            msg = None
        else:
            msg = dmsg.message
        super().__init__(description, msg)
