"""
Bidiretional json rpc implementation on stdout and stdin based on minimal rpc
implementation by Marcel Rieger, https://github.com/riga/jsonrpyc under MIT license:
Minimal python RPC implementation in a single file based on the JSON-RPC 2.0 specs from
http://www.jsonrpc.org/specification.

Adopted to work bidirectional and rewritten in some parts by Christoph Hechenblaikner,
https://github.com/chrihech, christoph@crosscloud.me
"""

import queue
import json
import time
import threading
import logging

__all__ = ["BidirectionalRPC"]

logger = logging.getLogger(__name__)


class Spec(object):
    """
    This class wraps methods that create JSON-RPC 2.0 compatible string representations
     of
    requests, responses, and errors. All methods are class members, so you might never
    want to
    create an instance of this class, but rahter use the methods directly:

    .. code-block:: python

       Spec.request("my_method", 18)
       # => '{"jsonrpc": "2.0", "method": "my_method", "id": 18}'

       Spec.response(18, "some_result")
       # => '{"jsonrpc": "2.0", "id": 18, "result": "some_result"}'

       Spec.error(18, -32603)
       # => '{"jsonrpc": "2.0", "id": 18, "error": {"code": -32603, "message": "Internal
       error"}}'
    """

    @classmethod
    def check_id(cls, message_id, allow_empty=False):
        """
        Value check for *id* entries. When *allow_empty* is *True*, *id* is allowed to
        be *None*.
        Raises a *TypeError* when *id* is not an interger and no string.
        """
        if allow_empty and message_id is None:
            return
        if not isinstance(message_id, (int, str)):
            raise TypeError("id must be an integer or string, got %s (%s)" %
                            (message_id, type(message_id)))

    @classmethod
    def check_method(cls, method):
        """
        Value check for *method* entries. Raises a *TypeError* when *method* is not a
        string.
        """
        if not isinstance(method, str):
            raise TypeError("method must be a string, got %s (%s)" %
                            (method, type(method)))

    @classmethod
    def check_code(cls, code):
        """
        Value check for *code* entries. Raises a *TypeError* when *code* is not an
        interger, or a
        *KeyError* when there is no :py:class:`RPCError` derivative registered for
        that *code*.
        """
        if not isinstance(code, int):
            raise TypeError("code must be an integer, got %s (%s)" % (code, type(code)))
        elif get_error(code) is None:
            raise KeyError("unknown code, got %s (%s)" % (code, type(code)))

    @classmethod
    def request(cls, method, message_id=None, params=None):
        """
        Creates the string representation of a request that calls *method* with optional
         *params*.
        When *id* is *None*, the request is considered a notification.
        """
        try:
            cls.check_method(method)
            cls.check_id(message_id, allow_empty=True)
        except Exception as exception:
            raise RPCInvalidRequest(str(exception))

        request = {'jsonrpc': '2.0', 'method': method}

        if message_id is not None:
            request['id'] = int(message_id)

        if params is not None:
            request['params'] = params

        return request

    @classmethod
    def response(cls, message_id, result):
        """
        Creates the string representation of a respons that was triggered by a
        request with *id*.
        *result* is required.
        """
        try:
            cls.check_id(message_id)
        except Exception as exception:
            raise RPCInvalidRequest(str(exception))

        response = {'jsonrpc': '2.0'}

        if message_id is not None:
            response['id'] = int(message_id)

        response['result'] = result

        return response

    @classmethod
    def error(cls, message_id, code, data=None):
        """
        Creates the string representation of an error that occured while processing
        a request with
        *id*. *code* must lead to a registered :py:class:`RPCError`. *data* might contain
        additional, detailed error information.
        """
        try:
            cls.check_id(message_id)
            cls.check_code(code)
        except Exception as exception:
            raise RPCInvalidRequest(str(exception))

        error = {'jsonrpc': '2.0'}

        if message_id:
            error['id'] = int(message_id)

        message = get_error(code).title
        error['code'] = code
        error['message'] = message
        error['data'] = data

        return error


# pylint: disable=too-many-instance-attributes
class BidirectionalRPC(object):
    """
    The main class of *jsonrpyc*. Instances of this class basically wrap an input
    stream *stdin* and
    an output stream *stdout* in order to communicate with other *services*. A
    service is not even
    forced to be written in Python as long as it strictly implements the JSON-RPC
    2.0 specs. RPC
    instances may wrap a *target* object. Incomming requests will be routed to
    methods of this
    object whose result might be sent back as a response. Example implementation:

    *server.py*

    .. code-block:: python

       import jsonrpyc

       class MyTarget(object):

           def greet(self, name):
               return "Hi, %s!" % name

       jsonrpc.RPC(MyTarget())

    *client.py*

    .. code-block:: python

        import jsonrpyc
        from subprocess import Popen, PIPE

        p = Popen(["python", "server.py"], stdin=PIPE, stdout=PIPE)
        rpc = jsonrpyc.RPC(stdout=p.stdin, stdin=p.stdout)

        # non-blocking remote procedure call with callback, js-like signature
        def cb(err, res=None):
            if err:
                throw err
            log("callback got: " + res)

        rpc("greet", args=("John",), callback=cb)

        # cb is called asynchronously which prints
        # => "callback got: Hi, John!"

        # blocking remote procedure call with 0.1s polling
        log(rpc("greet", args=("John",), block=0.1))
        # => "Hi, John!"


    .. py:attribute:: target

       The wrapped target object. Might be *None* when no object is wrapped, e.g.
       for the *client*
       RPC instance.

    .. py:attribute:: stdin

       The input stream, re-opened with ``"rb"``.

    .. py:attribute:: stdout

       The output stream, re-opened with ``"wb"``.

    .. py:attribute:: watch

       The :py:class:`Watchdog` instance that watches *stdin*.
    """

    EMPTY_RESULT = object()

    def __init__(self, in_stream, out_stream, server=None):
        super(BidirectionalRPC, self).__init__()

        self.server = server

        self.in_stream = in_stream
        self.out_stream = out_stream

        self.id_count = -1
        self._callbacks = {}

        self.read_buffer = {}
        self.write_buffer = queue.Queue()

        self.rpc_reader = RPCReader(self)
        self.rpc_writer = RPCWriter(self)

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def call(self, method, args=(), callback=None, block=0):
        """
        Performs an actual remote procedure call by writing a request representation
        (a string) to
        the output stream. The remote RPC instance uses *method* to route to the actual
         method to
        call with *args* and *kwargs*. When *callback* is set, it will be called with
        the result of
        the remote call. When *block* is larger than *0*, the calling thread is blocked
        until the
        result is received. In this case, *block* will be the poll interval.
        This mechanism emulates
        synchronuous return value behavior. When both, *callback* is *None* and *block*
        is *0* or
        less, the request is considered a notification and the remote RPC instance will
        not send a
        response.
        """

        if callback is not None or block > 0:
            self.id_count += 1
            message_id = self.id_count
        else:
            message_id = None

        if callback is not None:
            self._callbacks[message_id] = callback

        if block > 0:
            self.read_buffer[message_id] = self.EMPTY_RESULT
        params = args
        req = Spec.request(method, message_id=message_id, params=params)

        # writing message to send buffer
        logger.debug('writing message queue')
        self._write(json.dumps(req))

        if block > 0:
            while True:
                logger.debug('waiting for result')
                if self.read_buffer[message_id] != self.EMPTY_RESULT:
                    result = self.read_buffer[message_id]
                    del self.read_buffer[message_id]
                    if isinstance(result, Exception):
                        raise result
                    else:
                        return result
                time.sleep(block)

    def handle(self, line):
        """
        Handles an incomming *line* and dispatches the parsed object to the request,
        response, or
        error handler.
        """
        obj = json.loads(line)

        # dispatch to the correct handler
        if "method" in obj:
            # request
            self._handle_request(obj)
        elif "error" not in obj:
            # response
            self._handle_response(obj)
        else:
            # error
            self._handle_error(obj)

    def _handle_request(self, req):
        """
        Handles an incomming request *req*. When it containes an id, a response or error
         is sent
        back.
        """
        try:
            logger.debug('Request: %s', req)
            method = self._route(req["method"])
            params = req.get("params", [])

            def execute_function():
                """

                :return:
                """
                if isinstance(params, dict):
                    result = method(**params)
                else:
                    result = method(*params)
                if "id" in req:
                    res = Spec.response(req["id"], result)
                    self._write(json.dumps(res))

            executor = threading.Thread(target=execute_function, daemon=True)
            executor.start()

        except BaseException as exception:
            logger.exception('Error while handling request', exc_info=True)
            if "id" in req:
                if isinstance(exception, RPCError):
                    # pylint: disable=no-member
                    err = Spec.error(req["id"], exception.code, exception.data)
                else:
                    err = Spec.error(req["id"], -32603, str(exception))
                # pylint: disable=no-member
                self._write(json.dumps(err))

    def _handle_response(self, res):
        """
        Handles an incomming successful response *res*. Blocking calls are resolved and
        registered
        callbacks are invoked with the first error argument being set to *None*.
        """
        if res["id"] in self.read_buffer:
            self.read_buffer[res["id"]] = res["result"]
        if res["id"] in self._callbacks:
            callback = self._callbacks[res["id"]]
            del self._callbacks[res["id"]]
            callback(None, res["result"])

    def _handle_error(self, res):
        """
        Handles an incomming failed response *res*. Blocking calls throw an exception and
        registered callbacks are invoked with an exception and the second result argument
         set to
        *None*.
        """
        err = res["error"]
        error = get_error(err["code"])(err.get("data", err["message"]))

        if res["id"] in self.read_buffer:
            self.read_buffer[res["id"]] = error
        if res["id"] in self._callbacks:
            callback = self._callbacks[res["id"]]
            del self._callbacks[res["id"]]
            callback(error, None)

    def _route(self, method):
        """
        Returnes the actual method of the wrapped target object to be called when
        *method* is
        requested. Example:

        .. code-block:: python
           MyClassB(object):
               def foo(self):
                   return 123

           MyClassA(object):
               def __init__(self):
                   self.b = MyClassB()
               def bar(self):
                   return "test"

           rpc = RPC(MyClassA())

           rpc._route("bar")
           # => <bound method MyClassA.bar ...>

           rpc._route("b.foo")
           # => <bound method MyClassb.foo ...>
        """
        obj = self.server
        for part in method.split("."):
            if not hasattr(obj, part):
                break
            obj = getattr(obj, part)
        else:
            return obj
        raise RPCMethodNotFound(data=method)

    def _write(self, buf):
        """
        Writes a string *s* to the output stream.
        """
        self.write_buffer.put(buf, block=False)

    def shut_down(self):
        """shuts down the processing of message in either direction, cannot be
        restarted"""
        self.rpc_reader.stop()
        self.rpc_writer.stop()


class RPCReader(threading.Thread):
    """
    This class represents a thread that watches the input stream for incomming content.

    .. py:attribute:: rpc

       The :py:class:`RPC` instance.

    .. py:attribute:: name

       The thread's name.

    .. py:attribute:: interval

       The polling interval of the run loop.

    .. py:attribute:: daemon

       The thread's daemon flag.
    """

    DEFAULT_TIME_OUT_TOKEN = 'IAMTIMEOUT'

    def __init__(self, rpc, name="rpcreader", interval=0.1, start=True):
        super(RPCReader, self).__init__(name=name, daemon=True)

        self.rpc = rpc
        self.name = name
        self.interval = interval

        self._stop = threading.Event()

        if start:
            self.start()

    def start(self):
        """
        Starts with thread's activity.
        """
        super(RPCReader, self).start()

    def stop(self):
        """
        Stops with thread's activity.
        """
        self._stop.set()

    def run(self):
        stream = self.rpc.in_stream

        # reading while not stopped
        while not self._stop.is_set():
            # read line
            logger.debug('waiting for line')
            line = stream.readline()
            logger.debug('got line')
            if line:
                if line == self.DEFAULT_TIME_OUT_TOKEN:
                    continue
                else:
                    self.rpc.handle(line)
            else:
                self._stop.wait(self.interval)
        logger.debug('RPCReader stopped')


class RPCWriter(threading.Thread):
    """Thread class that writes to the stdout for IPC communication"""
    STOP_TOKEN = 0xDEAD

    def __init__(self, rpc, name="rpcwriter", interval=0.1, start=True):
        super(RPCWriter, self).__init__(name=name, daemon=False)

        self.name = name
        self.interval = interval

        self._stop = threading.Event()
        self.rpc = rpc

        if start:
            self.start()

    def start(self):
        """
        Starts with thread's activity.
        """
        super(RPCWriter, self).start()

    def stop(self):
        """
        Stops with thread's activity.
        """
        self.rpc.write_buffer.put(self.STOP_TOKEN)
        self._stop.set()

    def run(self):
        # writing loop
        while not self._stop.is_set():
            # extracting write message from queue
            message = self.rpc.write_buffer.get()

            if message == self.STOP_TOKEN:
                return

            # writing out message
            self.rpc.out_stream.write(message + "\n")
            self.rpc.out_stream.flush()


class RPCError(Exception):

    """
    Base class for RPC errors.

    .. py:attribute:: message

       The message of this error, i.e., ``"<title> (<code>)[, data: <data>]"``.

    .. py:attribute:: data

       Additional data of this error. Setting the data attribute will also change the
       message
       attribute.
    """

    def __init__(self, data=None):
        # pylint: disable=no-member
        message = "%s (%s)" % (self.title, self.code)
        if data is not None:
            message += ", data: " + str(data)
        self.message = message

        super(RPCError, self).__init__(message)

        self.data = data

    def __str__(self):
        return self.message


ERROR_MAP_DISTINCT = {}
ERROR_MAP_RANGE = {}


def is_range(code):
    """error handling support function"""
    return isinstance(code, tuple) \
        and len(code) == 2 \
        and all(isinstance(i, int) for i in code) \
        and code[0] < code[1]


def register_error(cls):
    """
    Decorator that registers a new RPC error derived from :py:class:`RPCError`.
    The purpose of
    error registration is to have a mapping of error codes/code ranges to error
    classes for faster
    lookups during error creation.

    .. code-block:: python

       @register_error
       class MyCustomRPCError(RPCError):
           code = ...
           title = "My custom error"
    """
    # it would be much cleaner to add a meta class to RPCError as a registry for codes
    # but in cpython exceptions aren't types, so simply provide a registry mechanism here
    if not issubclass(cls, RPCError):
        raise TypeError("'%s' is not a subclass of RPCError" % cls)

    code = cls.code

    if isinstance(code, int):
        error_map = ERROR_MAP_DISTINCT
    elif is_range(code):
        error_map = ERROR_MAP_RANGE
    else:
        raise ValueError("invalid RPC error code " + str(code))

    if code in error_map:
        raise AttributeError("duplicate RPC error code " + str(code))

    error_map[code] = cls

    return cls


def get_error(code):
    """
    Returns the RPC error class that was previously registered to *code*.
    *None* is returned when no
    class could be found.
    """
    if code in ERROR_MAP_DISTINCT:
        return ERROR_MAP_DISTINCT[code]

    for (lower, upper), cls in ERROR_MAP_RANGE.items():
        if lower <= code <= upper:
            return cls

    return None


@register_error
class RPCParseError(RPCError):
    """error class for events happening during the ipc communication when parsing a
    message (json) goes wrong"""
    code = -32700
    title = "Parse error"


@register_error
class RPCInvalidRequest(RPCError):
    """error class for events when an invalid request is sent"""
    code = -32600
    title = "Invalid Request"


@register_error
class RPCMethodNotFound(RPCError):
    """error class for when the requested method is not implemented by this end"""
    code = -32601
    title = "Method not found"


@register_error
class RPCInvalidParams(RPCError):
    """error class for when invalid parameters are passed to this end"""
    code = -32602
    title = "Invalid params"


@register_error
class RPCInternalError(RPCError):
    """error class for when the message could not be processed due to internal problems"""
    code = -32603
    title = "Internal error"


@register_error
class RPCServerError(RPCError):
    """error class for when the server at this end is not running properly"""
    code = (-32099, -32000)
    title = "Server error"
