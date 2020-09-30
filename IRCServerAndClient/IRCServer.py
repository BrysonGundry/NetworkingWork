# Bryson Gundry
# 10/25/2019 - Project 3 - IRCServer

from optparse import OptionParser
from socket import *
import os, sys
import selectors
import logging
import types

class IRCServer(object):

    # Initialization method
    def __init__(self, options, run_on_localhost=False):

        # TODO: Initialize any required code here
        self.sel = selectors.DefaultSelector()

        # DO NOT EDIT ANYTHING BELOW THIS LINE IN __init__
        # -----------------------------------------------------------------------------

        # You server socket should be assigned to this variable
        self.server_socket = None

        # Store all information about channels in this variable.
        # The key should be the channel name, and the variable a Channel object
        self.channels = {}

        # Store the users who are directly connected to this server
        # The list should contain the nick of the users
        self.adjacent_users = []

        # Store all information about users in this variable
        # The key should be the user's nick, and the variable a UserDetails object
        self.users_lookuptable = {}

        # Store the servers who are directly connected to this server
        # The list should contain the names of the servers
        self.adjacent_servers = []
        
        # Store all information about servers in this variable
        # The key should be the servername, and the variable a ServerDetails object
        self.servers_lookuptable = {}


        # The name, address,and port this server is running on
        self.servername = options.servername
        self.port = options.port
        # Human readable information about this server
        self.info = options.info
        

        # The first server started is the root node, and will not connect to any other servers
        # All other servers need to connect to another server on startup. That server's information
        # is stored in these variables.
        # The name of the server to connect to
        self.connect_to_host = options.connect_to_host
        # The address of the server to connect to. This is equal to the servername if NOT running on localhost,
        # and is equal to 127.0.0.1 if running on localhost
        self.connect_to_host_addr = options.connect_to_host
        # The port to connect to on the server
        self.connect_to_port = options.connect_to_port


        # If we're supposed to run this server on localhost, then change the connect_to_host_addr to 127.0.0.1
        self.run_on_localhost=run_on_localhost
        if self.run_on_localhost:
            self.connect_to_host_addr = '127.0.0.1'


        # Options to help with debugging and logging
        self.debug = options.debug
        self.verbose = options.verbose
        self.log_file = options.log_file
        self.logger = None
        self.init_logging()


        # This can be set to True to terminate the object
        self.request_terminate = False


        # This dictionary contains mappings from commands to command handlers.
        # Upon receiving a command X, the appropriate command handler can be called with: self.message_handlers[X](...args)
        self.message_handlers = {
            # Connection Registration message handlers
            "USER":self.handle_user_message,
            "SERVER":self.handle_server_message,
            "QUIT":self.handle_quit_message,
            # Channel operations
            "JOIN":self.handle_join_message,
            "PART":self.handle_part_message,
            "TOPIC":self.handle_topic_message,
            "NAMES":self.handle_names_message,
            # Sending messages
            "PRIVMSG":self.handle_privmsg_message,
            # Response handlers
            "331":self.handle_notopic_rpl,
            "332":self.handle_topic_rpl,
            "353":self.handle_names_rpl
        }

        # This dictionary maps human-readable reply/error messages to their numerical representations.
        # The numerical representation must be sent to clients, not the human-readable version. 
        # The full format for each reply/error message is included next to each command as a comment
        self.reply_codes = {
            "RPL_WELCOME": 1,           # :server_name ### :Welcome to the Internet Relay Network <nick>!<user>@<host>
            "RPL_NOTOPIC": 331,         # :server_name ### <channel> :No topic is set
            "RPL_TOPIC": 332,           # :server_name ### <channel> :<topic>            
            "RPL_NAMREPLY": 353,        # :server_name ### <channel> :nick1 nick2 nick3...
            "RPL_ENDOFNAMES": 366,      # :server_name ### <channel> :End of /NAMES list

            "ERR_NOSUCHNICK":401,       # :server_name ### <nick> :No such nick
            "ERR_CANNOTSENDTOCHAN":404, # :server_name ### <channel> :Cannot send to channel
            "ERR_NICKCOLLISION":436,    # :server_name ### <nick> :Nickname collision KILL from <user>@<host>
            "ERR_NEEDMOREPARAMS":461,   # :server_name ### <command> :Not enough parameters
            "ERR_BADCHANNELKEY":475,    # :server_name ### <channel> :Cannot join channel (+k)
            "ERR_NOSUCHCHANNEL":403,    # :server_name ### <channel> :No such channel
            "ERR_NOTONCHANNEL":442,     # :server_name ### <channel> :You're not on that channel            
        }


    # DO NOT EDIT THIS METHOD
    # Setup the server and start listening for incoming messages
    def run(self):
        self.print_info("Launching server %s..." % self.servername)
        # Set up the server socket that will listen for new connections
        self.setup_server_socket()

        # If we are supposed to connect to another server on startup, then do so now
        if self.connect_to_host and self.connect_to_port:
            self.connect_to_server()
        
        # Start listening for connections on the server socket
        self.listen(self.server_socket)
        

    # TODO: Create a TCP server socket and bind to the port defined in __init__.
    #       Begin listening for incoming connections and register the socket with your selector
    # HINT: You will need to differentiate between the server socket (which accepts new connections)
    #       and connections with other servers and clients. Select won't tell you which is which,
    #       it just tells you that a socket is ready for processing. You will need to store some information
    #       to let you distinguish the server socket from all other sockets
    def setup_server_socket(self):
        self.print_info("Configuring the server socket...")

        # Creating server socket
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.server_socket.bind(('', self.port))        
        self.server_socket.listen(1)
        self.server_socket.setblocking(False)
        selector_read_event = selectors.EVENT_READ

        # Setting the register to read in w/ string SERVER
        self.sel.register(self.server_socket, selector_read_event, "SERVER")

    # This function is responsible for connecting to a remote IRC server upon starting this server
    # The details of the server to connect to are set in self.connect_to_host_addr and self.connect_to_port
    # TODO: Establish a connection with the remote server, register the new socket with your selector,
    #       and send a SERVER registration message to the server you've connected to
    def connect_to_server(self):
        self.print_info("Connecting to remote server %s:%i..." % (self.connect_to_host, self.connect_to_port))

        # Initialzing socket
        client_socket = socket(AF_INET, SOCK_STREAM)
        client_socket.connect((self.connect_to_host_addr, self.connect_to_port))

        # Setting event to read / write
        event = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = ConnectionData()
        self.sel.register(client_socket, event, data)

        # String message for reading in
        message = "SERVER " + self.servername + " 1 :" + self.info + '\r\n'
        data.write_buffer += message
        data.write_buffer.encode()
        

    # This is the main loop responsible for processing input and output on all sockets this server
    # is connected to. You should manage these connections using a selector you have instantiated.
    # TODO: In side of the while not self.request_terminate loop, get a list of all sockets ready for processing
    #       from your selector, and then process these events. If the socket being processed is the server socket,
    #       call self.accept_new_connection. Otherwise, call self.service_socket.
    def listen(self, server_sockets):
        self.print_debug("Listening for new connections on port " + str(self.port))
        # All calls to select() MUST be inside of this loop. Select is a blocking call, and we need to terminate the 
        # server in order to test its functionality. We will accomplish this by calling select() inside of loop that
        # we can terminate by setting self.request_terminate to True.
        # You should also give select a relatively short timeout (try 1 second), so the program doesn't hang unnecessarily
        # when it comes time to terminate
        while not self.request_terminate:

            # handle case of no registered objects
            if len(self.sel._fd_to_key) == 0:
                continue

            events = self.sel.select(timeout=1)

            for key, mask in events:
                if key.data is not "SERVER":
                    self.service_socket(key, mask)
                else:
                    # if in server socket
                    self.accept_new_connection(key.fileobj)
                
        self.cleanup()

            # NOTE: You may encounter an error at this point where no fileobjs have yet been registered with your selector
            #       If you get an unexpected error here, try adding a check that there are fileobjs registered with your
            #       selector before calling select() 


    # This function will be called by the server before exiting, and will clean up anything that needs to be
    # cleaned before termination
    # TODO: Perform any cleanup required upon termination of the program. Think about what needs to be cleaned up for
    # sockets AND for selectors. 
    def cleanup(self):
        self.sel.close()
        self.server_socket.close()

    # This function is responsible for handling new connection requests from other servers and from clients. You
    # can't tell if the incoming connection request comes from a server or a client at this point
    # TODO: Accept the connection request and register it with your selector. You should configure all sockets
    #       for both READ and WRITE events. You will also need to create an instance of ConnectionData() and assign it
    #       to the data field when registering the connection. ConnectionData is a class created for this assignment.
    #       See the comments on that class for more details. You will use ConnectionData to keep track of important
    #       information about this connection
    def accept_new_connection(self, sock):
        conn, addr = sock.accept()

        event = selectors.EVENT_READ | selectors.EVENT_WRITE

        conn.setblocking(False)

        data = ConnectionData()

        self.sel.register(conn, event, data)

    # This function is responsible for handling IRC messages received from connected
    # servers and clients. 
    # TODO: Check to see if this is a READ event or/and a WRITE event (it is possible for it to be both).
    #       If it is a read event, read the data from the connection and process it. If you call recv but
    #       don't receive any data, this means that the client/server has closed their connection from
    #       the other side. In this case, you should unregister and close the socket.
    #       This is the ONLY function where send() and recv() should be called on a socket.
    def service_socket(self, key, mask):
        # Initializing socket and data
        self.print_debug("servicing socket")

        sock = key.fileobj 
        data = key.data

        # If server is reading
        if mask & selectors.EVENT_READ: 
            message = sock.recv(2048).decode()
            if not message:
                self.sel.unregister(sock)
                sock.close()
                self.print_debug("read")

            else:
                self.print_debug("message: " + message)
                self.process_data(key, message)

        # If server writing
        if mask & selectors.EVENT_WRITE:
            if len(data.write_buffer) is not 0:
                sock.send(data.write_buffer.encode())
                # Setting write buffer to clear
                data.write_buffer = ""
                self.print_debug("write")

    # This function should start the process of handling data received by the server. You will need to
    # perform several tasks:
    # 1. Split the data into distinct messages, in case the data in the recv buffer contains several commands
    # 2. Separate each message into three variables: prefix, command, and params
    #    prefix should be None if no prefix is present
    #    command should be a string containing the command word, or response number
    #    params should be a list containing the parameters included in the message. If no params
    #    we included, then params should be None
    # 3. After separating the prefix, command, and params, you should then call
    #    self.message_handlers[command](select_key, prefix, command, params) for each message
    #    This will call the correct function (defined below) for the message you have received
    # TODO: Write this function, including all of the functionality described above. You are encouraged
    #       to create several methods that are called by process_data to handle each of these required effects
    def process_data(self, select_key, recv_data):       
       # Splitting data 
        msgs = recv_data.split("\r\n")

        # Looping through each message that is recieved 
        for message in msgs:
            prefix = None
            params = []

            # Making sure each length of message is greater than 1
            if len(message) > 1:
                # Splitting the message into different partitions
                splitMessage = message.split(" ")

                # Seeing if message starts witha  prefix
                if message.startswith(":"):
                    # Splitting message and then popping / removing it
                    prefix = splitMessage[0][1:]
                    splitMessage.pop(0)

                # Setting Variables
                command = splitMessage[0]
                splitMessage.pop(0)

                # Testing each partition made within the message that was split previously
                for eachPartition in splitMessage:
                    # Testing each partition for a prefix
                    if eachPartition.startswith(":"):
                        # Setting each partition and appending it to the message
                        index = message.find(eachPartition)
                        params.append(message[index + 1:])
                        break
                    # Appending to message
                    else:
                        params.append(eachPartition)

                # Sending message / handling message via prompt above
                if params:
                    self.message_handlers[command](select_key, prefix, command, params)
                else:
                    self.message_handlers[command](select_key, prefix, command, None)

    ######################################################################
    # This block of functions should handle all functionality realted to how
    # the server sends messages. Avoid directly sending messages or responses
    # in the command handlers, and instead call these functions

    # This function should implement the functionality used to send a message to another server.
    # You CANNOT call send() in this function, or in a function directly called by this function.
    # Remember that send() must be called when handling a selector event with the WRITE mask set to true
    # TODO: Write the code required when the server has a message to be sent to another server
    def send_message_to_server(self, name_of_server_to_send_to, message):
        self.servers_lookuptable[name_of_server_to_send_to].write_buffer += message + "\r\n"

    # This function should implement the functionality used to send a message to a client. This function
    # will be slightly different from send_message_to_server(), as messages addressed to clients are first
    # forwarded to servers, and then sent to the user upon arriving at the server the user is registered to.
    # You CANNOT call send() in this function, or in a function directly called by this function.
    # Remember that send() must be called when handling a selector event with the WRITE mask set to true
    # TODO: Write the code required when the server has a message to be sent to a client
    def send_message_to_client(self, name_of_client_to_send_to, message):
        if name_of_client_to_send_to in self.users_lookuptable:
            clientInfo = self.users_lookuptable[name_of_client_to_send_to]

            if clientInfo.first_link:
                self.send_message_to_server(clientInfo.first_link, message)
            else:
                clientInfo.write_buffer += message + "\r\n"

    # When responding to an error, you may not yet know the name of client/server when sent the message
    # (E.g. when the initial registration command fails.) In this case, you will need to send the message
    # back using the select_key that was passed into your message handler. The functionality of this code
    # will be very similar to your send_message_to_server() function, but it will only be called
    # if you don't know the name of the server/client the message is directed to
    # TODO: Write the code required when the server has a message to be sent through a select_key
    def send_message_to_select_key(self, select_key, message):
        connData = select_key.data
        connData.write_buffer += message
        
    # Messages will sometimes need to be sent to every server in the IRC network. This is a helper function
    # to make that process easier. You may call send_message_to_server() in this function. Make sure you only
    # send the message to servers that are ADJACENT to this server. 
    # You will sometimes want to exclude a  server from receiving this message, such as when forwarding a message 
    # received from another server. In this case, you can't forward this message back to that server or the message 
    # will never die. This is the purpose of the ignore_server parameter. You must NOT broadcast a message
    # to the server included in that parameter, if it is present (it defaults to None).
    # TODO: Write the code required to broadcast to all adjacent servers, except for a server included in the
    #       ignore_server parameter
    def broadcast_message_to_servers(self, message, ignore_server=None):
        for server in self.adjacent_servers:
            if server != ignore_server:
                self.send_message_to_server(server, message)

    # This is a helper function that should ingest the name of the numeric reply you want to send, and the message
    # associated with that numeric reply, and will return a fully formatted numeric reply. The format for all 
    # numeric replies is--> :<server_name> <numeric code> <message>
    def create_numeric_reply(self, reply_key, message):
        code = self.reply_codes[reply_key]  
        return ":%s %d %s\r\n" % (self.servername, code, message)

    ######################################################################
    # The remaining functions are command handlers. Each command handler is documented with the functionality that 
    # must be supported. Each command handler expects to receive 4 parameters: 
    # * select_key: select_key contains the key value returned by select() for a specific connection. This contains
    #               the socket and the data associated with the socket upon registration with select
    # * prefix:     the prefix of the message to be processed. This should be None if no prefix was present
    # * command:    the command to be processed
    # * params:     a list of the parameters associated with the command. This should be None if no params were present
    

    ######################################################################
    # User message
    # Command: USER
    # Parameters: 
    #   <nick>: the requested nickname for the new user (nicks may NOT start with '#')
    #   <hostname>: the name of the computer this user is connecting from
    #   <servername>: the name of the server this user is connecting to
    #   [<realname>]: the real name of the user
    # Examples: 
    #   USER samwise bagend theshire.irc.com :Samwise Gamgee                        # This is an initial registration command coming from a new client
    #   :rivendale.irc.com USER samwise bagend theshire.irc.com :Samwise Gamgee     # This is a notification from a server about a new client
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS: The message is missing parameters
    #   ERR_NICKCOLLISION: A user with this nick is already registered somewhere on the network
    #   RPL_WELCOME: The registration was successful
    # Notes: 
    # This function handles the initial registrion process for new users. The user must provide a unique
    # nick on registration. If this nick is not unique, the function must return a ERR_NICKCOLLISION message.
    # Upon receipt of a valid registration method, this function should create a new UserDetails object containing 
    # this user's details. This should be stored in the users_lookuptable, using the user's nick as the key associated
    # with this new value. Finally, the server should then notify the client that they have registered, using the RPL_WELCOME message,
    # and should broadcast their message to all other servers to inform them of the user's registration.
    #
    # Additionally, the server the user registers directly with also needs to replace the ConnectionData associated with this socket
    # that was created in accept_new_connection(). It should replace ConnectionData with the new UserDetails object.
    # The ConnectionData object can be replaced using the selector.modify command (see python docs for more detail). This allows us
    # to determine that the connection received over that socket is from a client, and to determine which client, for all future
    # messages received from that socket
    def handle_user_message(self, select_key, prefix, command, params):

        # Setting variables to use in function
        user = UserDetails()
        user.nick = params[0]
        user.hostname = params[1]
        user.servername = params[2]
        user.realname = params[3]

        # Checking if there is a nickname collision, sending error message 436 as declared above
        if user.nick in self.users_lookuptable.keys():
            return 436

        # Checking if there is a prefix
        if prefix:
            user.first_link = prefix
            # Checking nickname in lookuptable, assigning to user of server
            self.users_lookuptable[user.nick] = user
            # Message to broadcast
            message = ":" + self.servername + " USER " + user.nick + " " + user.hostname + " " + user.servername + " :" + user.realname + "\r\n"
            # Sending message to servers to let them know
            self.broadcast_message_to_servers(message, prefix)

        else:
            user.first_link = user.servername
            # Appending user of server to adjacent servers
            self.adjacent_users.append(user.nick)
            # Checking nickname in lookuptable, assigning to user of server
            self.users_lookuptable[user.nick] = user
            # Message to broadcast
            message = ":" + self.servername + " USER " + user.nick + " " + user.hostname + " " + user.servername + " :" + user.realname + "\r\n"
            # Sending message to servers to let them know, and modifying 
            self.broadcast_message_to_servers(message, user.servername)
            self.sel.modify(select_key.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, user)
        

    ######################################################################
    # Server message
    # Command: SERVER
    # Parameters: 
    #   <servername>: the name of the new server
    #   <hopcount>: the number of hops required to reach this server
    #   [<info>]: human-readable name for the server
    # Examples: 
    #   SERVER rivendale.irc.edu 1 :The House of Elrond                     # This is an initial registration command coming from a new server
    #                                                                       # that should be connected to this server in the spanning tree
    #   :gondolin.irc.com SERVER rivendale.irc.edu 4 :The House of Elrond   # This is a notification from a known server about a new server
    #                                                                       # that has connected elsewhere into the spanning tree
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS: The message is missing parameters
    # Notes: 
    # This function handles the initial registrion process for new servers. The user must provide a unique servername
    # on registration. Upon receipt of a valid registration method, this function should create a new ServerDetails object containing 
    # this server's details. This should be stored in the servers_lookuptable, using the server's name as the key associated
    # with this new value. The server should then notify all other servers about this new server. 
    # 
    # Finally, the server should send the new server all known servers and users. This can be accomplished by sending 
    # SERVER and USER messages, and RPL_TOPIC/RPL_NOTOPIC and RPL_NAMEPLY messages, that inform the new server about every other
    # known server, user, and channel. Sending SERVER and USER messages will inform the new server about all servers and users 
    # using the normal registration code, and thus requires no additional development. You will need to complete the appropriate
    # RPL handlers for RPL_TOPIC, RPL_NOTOPIC, and RPL_NAMEPLY to enable the new server to register existing channel information.
    # These RPL handlers will only be used for this functionality.
    #
    # Additionally, the server the new server registers directly with also needs to replace the ConnectionData associated with this socket
    # that was created in accept_new_connection(). It should replace ConnectionData with the new ServerDetails object.
    # The ConnectionData object can be replaced using the selector.modify command (see python docs for more detail). This allows us
    # to determine that the connection received over that socket is from a server, and to determine which server, for all future
    # messages received from that socket
    def handle_server_message(self, select_key, prefix, command, params):
        # Variables for ease of use
        server = ServerDetails()
        server.servername = params[0]
        serverName = server.servername
        adjacentServers = self.servers_lookuptable
        allServerDetails = self.servername
    
        # To check if servername is already known
        if serverName in adjacentServers:
            return

        # To check if servername is equal to servername known
        if serverName == allServerDetails:
            return

        server.info = params[2]
        adjacentServers[serverName] = server

        # If prefix exists
        if prefix:
            prefix = server.first_link 
            # message to broadcast to adjacent servers
            message = ":" + allServerDetails + " SERVER " + serverName + " " + " :" + server.info
            self.broadcast_message_to_servers(message, prefix)

        # If prefix does not exist
        else:
            server.first_link = None
            # message to broadcast to adjacent servers
            message = ":" + allServerDetails + " SERVER " + serverName + " " + " :" + server.info

            # Setting event to read and write
            event = selectors.EVENT_READ | selectors.EVENT_WRITE
            self.sel.modify(select_key.fileobj, event, server)
            
            # Adding servername to adjacent server list, then broadcasting to other
            self.adjacent_servers.append(serverName)
            self.broadcast_message_to_servers(message, serverName)

        for currentUser, listOfUsers in self.users_lookuptable.items():
            # Variables to use in message...
            hostName = listOfUsers.hostname
            currentServerName = listOfUsers.servername
            realNameOfUser = listOfUsers.realname

            # message to send to server
            message = ":" + allServerDetails + " USER " + currentUser + " " + hostName + " " + currentServerName + " :" + realNameOfUser
            self.send_message_to_server(currentServerName, message)

        for currentServerName, listOfAdjacentServers in adjacentServers.items():
            # Variables to use in message...
            adjacentServersInfo = listOfAdjacentServers.info

            # message to send to server
            message = ":" + allServerDetails + " SERVER " + currentServerName + " " + " :" + adjacentServersInfo
            self.send_message_to_server(serverName, message)

        # message to send to server
        message = "SERVER " + allServerDetails + " " + " :" + self.info
        self.send_message_to_server(serverName, message)

    ######################################################################
    # Quit message
    # Command: QUIT
    # Parameters: 
    #   {[<Goodbye message>]}: an optional message from the user who has quit. If no message is provided,  
    #                     use the default message: <nick> has quit  
    # Examples: 
    #   QUIT :shot with an arrow in the chest               # A message from a user who is quitting the server
    #   :boromir QUIT :shot with an arrow in the chest      # A message from another server about a user who has quit. The user's 
    #                                                       # nick is included in the prefix of the message
    # Numeric replies: 
    #   None
    # Notes: 
    # This function should be called when a user quits the IRC network. All information of this user should be removed from
    # users_lookuptable and adjacent_users, as well as any channels the user had joined. The Quit message must then be broadcast
    # to all servers. If the user appended an optional Goodbye message then it should be sent to all users in the channels
    # the user had joined.
    def handle_quit_message(self, select_key, prefix, command, params):
        # If prefix doesn't exist 
        if prefix is None:
            nick = select_key.data.nick

            # Checking nickname in adjacent users
            if nick in self.adjacent_users:
                self.adjacent_users.remove(nick)

            # Checking nickname in lookuptable of users
            if nick in self.users_lookuptable.keys():
                self.users_lookuptable.pop(nick)

            trailing_params = ""
            # Checking params in user
            for user in params:
                if(user == params[0]):
                    trailing_params += ":" + user

                else:
                    trailing_params += " " + user

            # Adding ending to trailing params, creating a message, and broadcasting to servers
            trailing_params += "\r\n"
            message = ":" + nick + " " + command + " " + trailing_params
            self.broadcast_message_to_servers(message, select_key.data.servername)

        else:
            nick = prefix
            # If nick doesn't follow suit of other cases - needed to add this or test crashed
            if nick not in self.adjacent_users and nick not in self.users_lookuptable.keys():
                return

            # If nickname is in adjacent users, remove the nickname
            if nick in self.adjacent_users:
                self.adjacent_users.remove(nick)

            # If nickname is in lookuptable, remove the nickname
            if nick in self.users_lookuptable.keys():
                self.users_lookuptable.pop(nick)

            trailing_params = ""

            # For user in parameters
            for user in params:
                if(user == params[0]):
                    trailing_params += ":" + user
                else:
                    trailing_params += " " + user
            trailing_params += "\r\n"
            
            # Sending message and broadcasting it to servers
            message = ":" + nick + " " + command + " " + trailing_params
            self.broadcast_message_to_servers(message, prefix)
  
    ######################################################################
    # Join message
    # Command: JOIN
    # Parameters: 
    #   <channel>: The name of the channel being joined. Note: Channel names must start with '#'
    #   [<channel key>]: The password required to join this channel
    # Examples: 
    #   JOIN #Orcs4Isengard             # Join the channel #Orcs4Isengard without a password, 
    #                                   # or create the channel if it does not exist 
    #   JOIN #Orcs4Isengard fubar       # Join the channel #Orcs4Isengard with the password fubar, 
    #                                   # or create the channel with that password if it does not exist
    #   :Saruman JOIN #Orcs4Isengard    # Message from another server telling this server that
    #                                   # the user Saruman has joined the channel
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS
    #   ERR_BADCHANNELKEY
    #   RPL_TOPIC
    #   RPL_NOTOPIC
    # This function should be called when a user attempts to join a channel. If the user attempts to join a channel that does
    # not exist, then the channel should be created. The server must create a Channel object and store it in channels using the
    # name of the channel as the key. 
    # Users may specify a channel key (i.e. a password). If this is specified when
    # the channel is created, all future join requests to that channel must include the correct key. If the wrong key is provided,
    # the server must return a ERR_BADCHANNELKEY response.
    # Upon joining a channel, the server must return a RPL_TOPIC response with the current topic of this channel, or a RPL_NOTOPIC
    # response if no topic has been set for the channel.
    # Finally, the server must broadcast the fact that the user has joined this channel to all other servers. The server does NOT
    # inform users connected to this channel that a new user has joined. The user must call NAMES to fetch that information.
    def handle_join_message(self, select_key, prefix, command, params):
        pass




    ######################################################################
    # Part message
    # Command: PART
    # Parameters: 
    #   <channel>: The name of the channel to leave
    # Examples: 
    #   PART #Orcs4Isengard             # Leave the channel #Orcs4Isengard
    #   :Saruman PART #Orcs4Isengard    # Message from another server telling this server that
    #                                   # the user Saruman has left the channel
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS 
    #   ERR_NOSUCHCHANNEL
    #   ERR_NOTONCHANNEL 
    # This function should be called when a user attempts to leave a channel. If the user attempts to leave a channel that it
    # is not registered to, the server should return a ERR_NOTONCHANNEL response. If the user attempts to leave a channel that
    # does not exist, then the server should return a ERR_NOSUCHCHANNEL response.
    # Upon leaving, the user should be removed from the appropriate Channel object, and all other servers should be informed
    # of the user's departure from this channel.
    def handle_part_message(self, select_key, prefix, command, params):
        pass




    ######################################################################
    # Topic message
    # Command: TOPIC
    # Parameters: 
    #   <channel> 
    #   [<topic>]
    # Examples: 
    #   TOPIC #RingBearers                              # Request the topic for the channel #RingBearers
    #   TOPIC #RingBearers :Best uses for invisibility  # Sets the topic for the channel #RingBearers to 
    #                                                   # Best uses for invisibility
    #   :Bilbo TOPIC #RingBearers :Best uses for invisibility   # Message from another server telling this
    #                                                           # server that the user Biblo has changed
    #                                                           # to topic #RingBearers
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS, 
    #   ERR_NOSUCHCHANNEL
    #   ERR_NOTONCHANNEL 
    #   RPL_NOTOPIC 
    #   RPL_TOPIC
    # This function allows a user to set or request the topic of a specific channel. If the server receives a TOPIC
    # command without a trailing argument, it should return the current topic of the channel to the client using either
    # RPL_TOPIC or RPL_NOTOPIC, as appropriate. If the server receives a TOPIC command WITH a trailing argument, it should
    # change the topic of the channel and inform all servers of the change in topic for this channel. All users connected
    # to this channel should also be notified of the change in topic.
    # If the server receives a message for a channel the user is not registered for, it should return a ERR_NOTONCHANNEL
    # response. If the server receives a message for a channel that does not exist, it should return a ERR_NOSUCHCHANNEL response.
    def handle_topic_message(self, select_key, prefix, command, params):   
        pass




    # This is a response handler, which is called when a new server is sent a NOTOPIC rpl from an existing server
    # This message contains the name of a channel and the information that no topic has been set at the time
    # this server is started. This method will be much simpler than most other message handlers
    # TODO: Create the new channel and initialize it.
    # NOTE: This design cannot accomodate setting keys for existing servers. Set the key to null. This is a bug
    #       that would need to be fixed if this code were to be deployed
    def handle_notopic_rpl(self, select_key, prefix, command, params):
        pass



    
    # This is a response handler, which is called when a new server is sent a TOPIC rpl from an existing server
    # This message contains the name of a channel and the topic that has been set at the time
    # this server is started. This method will be much simpler than most other message handlers
    # TODO: Create the new channel and initialize it.
    # NOTE: This design cannot accomodate setting keys for existing servers. Set the key to null. This is a bug
    #       that would need to be fixed if this code were to be deployed
    def handle_topic_rpl(self, select_key, prefix, command, params):
        pass




    ######################################################################
    # Names message
    # Command: NAMES
    # Parameters: 
    #   [<channel>]
    # Examples: 
    #   NAMES
    #   NAMES #RingBearers
    # Numeric replies:  
    #   ERR_NOSUCHCHANNEL,
    #   RPL_NAMREPLY,       # Send a separate RPL_NAMREPLY for each channel, listing the nicks in that channel, separated by spaces
    #   RPL_ENDOFNAMES      # Inform the user that there are no more RPL_NAMREPLY message coming
    # This function allows a user to request the name of all users in a given channel, or the name of all users in the IRC network.
    # If the server receives a NAMES command that includes a channel name, it should return the names of all users in that channel.
    # If the server receives a NAMES command without a channel name, it should return multiple messages: 1 message per channel
    # containing the names of all users in that channel, and 1 message containing the names of all users not in a channel.
    # This message should use the RPL_NAMREPLY format, but should set the channel name to '*'. Upon sending the last RPL_NAMREPLY
    # message, the server should then send a RPL_ENDOFNAMES response.
    # If the user requests the users on a channel that does not exist, return a ERR_NOSUCHCHANNEL response.
    def handle_names_message(self, select_key, prefix, command, params):
        pass




    # This is a response handler, which is called when a new server is sent a NAMES rpl from an existing server
    # This message contains information about the users who are registered with an existing channel at the time
    # this server is started. This method will be much simpler than most other message handlers
    # TODO: Add the users to the appropriate channel
    def handle_names_rpl(self, select_key, prefix, command, params):
        pass




    ######################################################################
    # Private message 
    # Command: PRIVMSG
    # Parameters: 
    #   <receiver>: The name of the entity the message is being sent to. This could be a user's nick, or a channel name
    #   <text to be sent>: The message to be sent
    # Examples: 
    #   PRIVMSG Angel :Hello are you receiving this message ?       # A command sending a message to user Angel
    #   :Angel PRIVMSG Wiz :I sure am!                              # Angel responding to Wiz's message
    #   PRIVMSG #RingBearers :So whose got the ring now?            # A command sending a message to a channel
    #   :Gollum PRIVMSG #RingBearers :So whose got the ring now?    # A message from Gollum forward to the channel #RingBearers
    # Numeric replies:  
    #   ERR_NEEDMOREPARAMS,
    #   ERR_NOSUCHNICK, 
    #   ERR_NOSUCHCHANNEL
    #   ERR_CANNOTSENDTOCHAN
    # This function allows users to send messages to other users, or to a channel. Upon receiving a message, the server
    # should first determine if this is addressed to a specific client, or to a channel. It should then forward the message
    # towards its destination. In addition to forwarding the message to other servers, each server must check to make sure 
    # if a user this message is addressed to is adjacent to it, and if so forward this message to that client. When sending
    # a message to a channel, the server must check to see if any of the users in the channel are adjacent.
    # If the server does not recognize the nick the message is addressed to, it should return a ERR_NOSUCHNICK response.
    # If the server does not recognize the channel the message is addressed to, it should return a ERR_NOSUCHCHANNEL response.
    # If the user sending the message is not part of the addressed channel, the server should return a ERR_NOSUCHCHANNEL response.
    def handle_privmsg_message(self, select_key, prefix, command, params):
        pass




    # DO NOT EDIT ANY OF THE FUNCTIONS INCLUDED IN IRCServer BELOW THIS LINE
    # These are helper functions to assist with logging, and list management
    # ----------------------------------------------------------------------


    ######################################################################
    # This block of functions enables logging of info, debug, and error messages
    # Do not edit these functions. init_logging() is already called by the template code
    # You are encouraged to use print_info, print_debug, and print_error to log
    # messages useful to you in development

    def init_logging(self):
        # If we don't include a log file name, then don't log
        if not self.log_file:
            return

        # Get a reference to the logger for this program
        self.logger = logging.getLogger("IRCServer")

        # Create a file handler to store the log files
        fh = logging.FileHandler(self.log_file, mode='w')

        # Set up the logging level. It defaults to INFO
        log_level = logging.INFO
        if self.debug:
            log_level = logging.DEBUG
        
        # Define a formatter that will be used to format each line in the log
        formatter = logging.Formatter(
            ("%(asctime)s - %(name)s[%(process)d] - "
             "%(levelname)s - %(message)s"))

        # Assign all of the necessary parameters
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        self.logger.setLevel(log_level)
        self.logger.addHandler(fh)

    def print_info(self, msg):
        if self.verbose:
            print("%s:%s" % (self.servername,msg))
            sys.stdout.flush()
        if self.logger:
            self.logger.info(msg)

    def print_debug(self, msg):
        if self.debug:
            print("%s:%s" % (self.servername,msg))
            sys.stdout.flush()
        if self.logger:
            self.logger.debug(msg)

    def print_error(self, msg):
        sys.stderr.write("%s:%s\n" % (self.servername, msg))
        if self.logger:
            self.logger.error(msg)



    # This function takes two lists and returns the union of the lists. If an object appears in both lists,
    # it will only be in the returned union once.
    def union(self, lst1, lst2): 
        final_list = list(set(lst1) | set(lst2)) 
        return final_list

    # This function takes two lists and returns the intersection of the lists.
    def intersect(self, lst1, lst2): 
        final_list = list(set(lst1) & set(lst2)) 
        return final_list

    # This function takes two lists and returns the objects that are present in list1 but are NOT
    # present in list2. This function is NOT commutative
    def diff(self, list1, list2):
        return (list(set(list1) - set(list2)))




# This class represents a channel. 
# You do not need to add any code to this class, though
# you may if you want to. You must NOT REMOVE OR RENAME any of the code or properties currently
# defined in this class.
class Channel(object):
    def __init__(self):  
        self.channelname = None     # The name of the channel      
        self.key = None             # The channel key (i.e. password)
        self.users = []             # The nicks of all users present in this channel
        self.topic = None           # The current topic of this channel. If no topic is present, it should be None

    # Append the nick if it's not already in the list. When adding a nick to the channel,
    # you are encouraged to use this function so as to avoid adding a user multiple times
    def add_nick(self, nick):
        if nick not in self.users:
            self.users.append(nick)




# This class represents a generic connection. It contains a read_buffer and a write_buffer. When the server wants to
# send a message to the client, it should write the message to the write_buffer, and use \r\n as a message delimiter.
# Then, when select() determines the socket associated with ConnectionData is ready to be written, it should write
# the write_buffer to the socket and clear it.
# Similarly, when reading from a socket in select(), the data should be stored in read_buffer and then processed.
# You do not need to add any code to this class, though you may if you want to. You must NOT REMOVE OR RENAME any 
# of the code or properties currently defined in this class.
class ConnectionData(object):
    def __init__(self):
        self.read_buffer = ""
        self.write_buffer = ""        




# UserDetails extends ConnectionData with properties specific to a connection with a user. As UserDetails extends 
# ConnectionData, it also contains read_buffer and write_buffer properties. 
# You do not need to add any code to this class, though you may if you want to. You must NOT REMOVE OR RENAME any 
# of the code or properties currently defined in this class.
class UserDetails(ConnectionData):    
    def __init__(self):
        super(UserDetails, self).__init__()
        self.nick = None
        self.hostname = None
        self.servername = None
        self.realname = None
        self.first_link = None




# ServerDetails extends ConnectionData with properties specific to a connection with a server. As ServerDetails extends 
# ConnectionData, it also contains read_buffer and write_buffer properties. 
# You do not need to add any code to this class, though you may if you want to. You must NOT REMOVE OR RENAME any 
# of the code or properties currently defined in this class.
class ServerDetails(ConnectionData):
    def __init__(self):
        super(ServerDetails, self).__init__()
        self.servername = None  # The name of the server
        self.hopcount = None    # The number of hops this server is away from the server who created this instance
        self.info = None        # A human-readable description of the server

        self.first_link = None  # The name of the server on the first link towards this server. This is a VERY important
                                # field, as you will use it to broadcast messages throughout the network.
                                # Assume a network structured as shown to the right:            ---A---
                                # Each server shown hear contains a ServerDetails for           |     |
                                # each other server in the network. D's configuration        C--B     D--E
                                # puts the name for A in the first_link property for B                |
                                # and C, as to deliver a message to B or C, D must send               F
                                # the message to A, who then forwards it to B.
                                # D has the name of F in the first_link property for F,
                                # since D must send a message addressed to F along the link
                                # for F. To send a message to C, D must write the message into
                                # the write_buffer associated with A. D can determine this
                                # by checking to see that the first_link property for C is
                                # the name of A, and then look A up in the servers_lookuptree.