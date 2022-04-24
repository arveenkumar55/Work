import fcntl
import logging
import os
import selectors
import sys
import threading

from socket import socket, gethostname, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SHUT_WR

from typing import Optional, List, TextIO

logging.basicConfig(filename="m.log",
                    filemode='a',
                    format='%(asctime)s.%(msecs)d %(levelname)s/%(name)s::%(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.ERROR)


class Arguments:
    """Contains all the arguments taken from the commandline"""

    listening: bool
    port: int
    host: str

    def __init__(self, listening: bool, port: int, host: str):
        self.listening = listening
        self.port = port
        self.host = host


class EventLoop:
    """A global loop to ensure the threads are synced when the server/client receives termination

    Build on the concept of Python GIL (Global Interpreter Lock)
    """

    __lock: threading.Lock
    __running: bool = True

    def __init__(self):
        self.__lock = threading.Lock()

    @property
    def is_running(self):
        """Acquires the lock and check the status if the loop is running"""

        status: bool
        with self.__lock:
            status = self.__running

        return status

    def stop(self) -> None:
        """Acquires the lock and update the loop status to not running"""

        logging.info(f"{args.listening} EventLoop.stop() called")
        with self.__lock:
            self.__running = False


def send(soc: socket, contents: str) -> None:
    """A simple function to abstract the sent bytes using socket"""

    soc.sendall(contents.encode('utf-8'))


def receive(soc: socket) -> Optional[str]:
    """A simple function to abstract the bytes received from the socket"""

    data = soc.recv(128)
    if data is None:
        logging.debug(f'{args.listening} ==> (user_in) {data} [Data is none]')
        return None

    return data.decode('utf-8')


def safe_unregister(fileobj) -> None:
    """Wrapper around selector.unregister that handles multiple unregister gracefully"""

    try:
        selector.unregister(fileobj)
    except (KeyError, ValueError):
        pass


def configure_non_blocking_input(soc: socket) -> None:
    """A function that configure the stdin to be non-blocking and using selectors to multiplex the receiving of data

    This function only works on Linux due to fcntl library. Instead of using threads for input, it leverages os
    level structures to provide non-blocking input, both improving performance and reliability.
    """

    orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

    # Create a function to register in the callback of selectors
    def user_in(stream: TextIO, mask) -> None:
        # Check if the stream can be read
        if not stream.closed and stream.readable():
            data = stream.read()
            # If the data sent is 0, that means the stream has ended
            if len(data) == 0:
                # Start the shutdown sequence
                shutdown(soc)
                return

            logging.debug(f'{args.listening} ==> (user_in) {data} {[d for d in data]}')
            # Send the data to the socket
            send(soc, data)
        else:
            shutdown(soc)

    # Register the callback to be called when new data comes in the given file object
    selector.register(sys.stdin, selectors.EVENT_READ, user_in)


def configure_non_blocking_output(soc: socket) -> None:
    """A function that configure the soc to be non-blocking and using selectors to multiplex the receiving of data

    Instead of using threads for output, it leverages os level structures to provide non-blocking output,
    both improving performance and reliability.
    """

    # Create the callback to be passed to selector
    def read(soc: socket, mask) -> None:
        # Get data from the socket
        data = receive(soc)
        logging.debug(f'{args.listening} <== (read) {data} {[d for d in data]}')
        # If the data is falsy or its length is zero
        if not data or len(data) == 0:
            # Initialize the shutdown sequence
            shutdown(soc)
            return

        # Output the contents sent by the server
        print(data, end='')

    # Register the callback to be called when the socket gets new content
    selector.register(soc, selectors.EVENT_READ, read)


def shutdown(soc: socket):
    """A simple cleanup that remove all the file objects from the selectors and close them, if any"""

    loop.stop()
    safe_unregister(soc)
    safe_unregister(sys.stdin)
    try:
        # Flush the contents in receive buffer to output stream
        data = receive(soc)
        while data is not None and data != '':
            print(data, end='')
            data = receive(soc)

    except:
        pass

    sys.stdin.close()


def start_event_loop() -> None:
    """Start the event loop

    TODO: Move this function to EventLoop
    """

    while loop.is_running:
        for k, mask in selector.select():
            callback = k.data
            callback(k.fileobj, mask)


def create_server(ip: str, port: int) -> socket:
    """Create a socket that binds to a socket"""
    soc = socket(AF_INET, SOCK_STREAM)
    soc.bind((ip, port))
    return soc


class Server:
    """A simple server object that creates the necessary tcp sockets and configure them"""

    soc: socket
    conn: socket
    running: bool = True

    def __init__(self, port: int) -> None:
        # Create the tcp base socket
        self.soc = create_server(gethostname(), port)
        # Set it to non blocking mode
        self.soc.setblocking(False)
        # Start listening for connections
        self.soc.listen()

    def accept(self, sock: socket, mask) -> None:
        self.conn, _ = sock.accept()
        # The incoming socket is set to blocking (due to inconsistent syncing bugs)
        self.conn.setblocking(True)
        # Configure the input and output
        configure_non_blocking_input(self.conn)
        configure_non_blocking_output(self.conn)

    def start(self) -> None:
        # Attach this to the selector
        selector.register(self.soc, selectors.EVENT_READ, self.accept)
        # Start the event loop
        start_event_loop()

        # Close the tcp socket once the event loop ends
        self.soc.shutdown(SHUT_WR)


def create_connection(ip: str, port: int) -> socket:
    """Create a socket that connects to a server socket"""
    soc = socket(AF_INET, SOCK_STREAM)
    soc.connect((ip, port))
    return soc


class Client:
    """A simple server object that creates the necessary tcp socket and configure them"""
    soc: socket
    running: bool = True

    def __init__(self, hostname: str, port: int) -> None:
        # Create the tcp socket
        self.soc = create_connection(hostname, port)
        # Set it to be reusable
        self.soc.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        # Set it to non-blocking
        self.soc.setblocking(False)

    def start(self) -> None:
        # Configure the input and output
        configure_non_blocking_input(self.soc)
        configure_non_blocking_output(self.soc)

        # Start the event loop
        start_event_loop()
        self.soc.shutdown(SHUT_WR)


def parse_args(argv: List[str]) -> Arguments:
    """Using sys.argv, detect the argument for the program"""
    argv = argv[1:]
    listening = argv[0] == '-l'
    if listening:
        argv = argv[1:]

    port = argv[0]
    host = gethostname()
    if len(argv) == 2:
        host = argv[1]

    return Arguments(listening, int(port), host)


if __name__ == '__main__':
    # Configure the shared thread states
    selector = selectors.DefaultSelector()
    loop = EventLoop()
    # Parse the arguments
    args = parse_args(sys.argv)

    # Launch the server or client
    if args.listening:
        Server(args.port).start()
    else:
        Client(args.host, args.port).start()
