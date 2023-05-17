import json
import urllib.parse
import asyncio
import websockets
import textwrap

from typing import List
from typing import Union
from websockets import exceptions, client
# from websockets import exceptions as ws_exceptions
from fields import STREAM_FIELD_IDS, CSV_FIELD_KEYS


class TdStreamerClient:

    def __init__(self, websocket_url=None, principal_data=None, credentials=None):
        self.websocket_url = f"wss://{websocket_url}/ws"
        self.credentials = credentials
        self.principal_data = principal_data
        self.data_requests = {'requests': []}
        self.fields_ids_dictionary = STREAM_FIELD_IDS
        self.csv_keys_dictionary = CSV_FIELD_KEYS
        self.loop = None
        self.connection: client.WebSocketClientProtocol = None
        self.print_to_console = True

        try:
            self.loop = asyncio.get_event_loop()
        except websockets.WebSocketException:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.unsubscribe_count = 0

    def _build_login_request(self):
        # define a request
        login_request = {
            "requests": [
                {
                    "service": "ADMIN",
                    "requestid": "0",
                    "command": "LOGIN",
                    "account": self.principal_data['accounts'][0]['accountId'],
                    "source": self.principal_data['streamerInfo']['appId'],
                    "parameters": {
                        "credential": urllib.parse.urlencode(self.credentials),
                        "token": self.principal_data['streamerInfo']['token'],
                        "version": "1.0"
                    }
                }
            ]
        }

        return json.dumps(login_request)

    def _build_data_request(self) -> str:
        """Builds the data request for the streaming service.
        Takes all the service requests and converts them to a JSON
        string.
        Returns:
        ----
        [str] -- A JSON string with the login details.
        """

        return json.dumps(self.data_requests)

    def stream(self, print_to_console: bool = True) -> None:
        """Starts the stream and prints the output to the console.
        Initalizes the stream by building a login request, starting
        an event loop, creating a connection, passing through the
        requests, and keeping the loop running.
        Keyword Arguments:
        ----
        print_to_console {bool} -- Specifies whether the content is to be printed
            to the console or not. (default: {True})
        """

        # Print it to the console.
        self.print_to_console = print_to_console

        # Connect to the Websocket.
        self.loop.run_until_complete(self._connect())

        # Send the Request.
        asyncio.ensure_future(self._send_message(self._build_data_request()))

        # Start Recieving Messages.
        asyncio.ensure_future(self._receive_message(return_value=False))

        # Keep the Loop going, until an exception is reached.
        self.loop.run_forever()

    async def build_pipeline(self) -> websockets.WebSocketClientProtocol:
        """Builds a data pipeine for processing data.
        Often we want to take the data we are streaming and
        use it in other functions or store it in other platforms.
        This method makes the process of building a pipeline easy
        by handling all the connection setup and request setup.
        Returns:
        ----
        websockets.WebSocketClientProtocol -- The websocket connection.
        """

        # In this case, we don't want things printing to the console.
        self.print_to_console = False

        # Connect to Websocket.
        await self._connect()

        # Build the Data Request.
        await self._send_message(self._build_data_request())

        return self.connection

    async def start_pipeline(self) -> dict:
        """Recieves the data as it streams in.
        Returns:
        ----
        dict -- The data coming from the websocket.
        """

        return await self._receive_message(return_value=True)

    async def _connect(self) -> websockets.WebSocketClientProtocol:
        """Connects the Client to the TD Websocket.
        Connecting to webSocket server websockets.client.connect
        returns a WebSocketClientProtocol, which is used to send
        and receive messages
        Keyword Arguments:
        ----
        pipeline_start {bool} -- This is also used to start the data
            pipeline so, in that case we can handle more tasks here.
            (default: {True})
        Returns:
        ---
        websockets.WebSocketClientProtocol -- The websocket connection.
        """

        # Grab the login info.
        login_request = self._build_login_request()

        # Create a connection.
        self.connection = await websockets.client.connect(self.websocket_url)

        # See if we are connected.
        is_connected = await self._check_connection()

        # If we are connected then login.
        if is_connected:

            await self._send_message(login_request)

            while True:

                # Grab the Response.
                response = await self._receive_message(return_value=True)
                responses = response.get('response')

                # If we get a code 3, we had a login error.
                if responses[0]['content']['code'] == 3:
                    raise ValueError('LOGIN ERROR: ' + responses[0]['content']['msg'])

                # see if we had a login response.
                for r in responses:
                    if r.get('service') == 'ADMIN' and r.get('command') == 'LOGIN':
                        return self.connection

    async def _check_connection(self) -> bool:
        """Determines if we have an active connection
        There are multiple times we will need to check the connection
        of the websocket, this function will help do that.
        Raises:
        ----
        ConnectionError: An error is raised if we can't connect to the
            websocket.
        Returns:
        ----
        bool -- True if the connection healthy, False otherwise.
        """

        # if it's open we can stream.
        if self.connection.open:
            print('CONNECTION ESTABLISHED. STREAMING WILL BEGIN SHORTLY.')
            print('='*80)
            return True
        elif self.connection.close:
            print('CONNECTION WAS NEVER OPENED AND WAS CLOSED.')
            return False
        else:
            raise ConnectionError

    async def _send_message(self, message: str):
        """Sends a message to webSocket server
        Arguments:
        ----
        message {str} -- The JSON string with the
            data streaming service subscription.
        """

        await self.connection.send(message)

    async def _receive_message(self, return_value: bool = False) -> dict:
        """Recieves and processes the messages as needed.
        Keyword Arguments:
        ----
        return_value {bool} -- Specifies whether the messages should be returned
            back to the calling function or not. (default: {False})
        Returns:
        ----
        {dict} -- A python dictionary
        """

        # Keep going until cancelled.
        while True:

            try:

                # Grab the Message
                message = await self.connection.recv()

                # Parse Message
                message_decoded = await self._parse_json_message(message=message)

                if return_value:
                    return message_decoded

                elif self.print_to_console:
                    print('=' * 20)
                    print('Message Received:')
                    print('-' * 20)
                    print(message_decoded)
                    print('-' * 20)
                    print('')

            except websockets.exceptions.ConnectionClosed:

                # stop the connection if there is an error.
                await self.close_stream()
                break

    async def _parse_json_message(self, message: str) -> dict:
        """Parses incoming messages from the stream
        Arguments:
        ----
        message {str} -- The JSON string needing to be parsed.
        Returns:
        ----
        dict -- A python dictionary containing the original values.
        """

        try:
            message_decoded = json.loads(message)
        except:
            message = message.encode('utf-8').replace(b'\xef\xbf\xbd', bytes('"None"','utf-8')).decode('utf-8')
            message_decoded = json.loads(message)

        return message_decoded


    async def heartbeat(self) -> None:
        """Sending heartbeat to server every 5 seconds."""

        while True:
            try:
                await self.connection.send('ping')
                await asyncio.sleep(5)
            except websockets.exceptions.ConnectionClosed:
                self.close_stream()
                break

    def _new_request_template(self) -> dict:
        """Serves as a template to build new service requests.
        This takes the Request template and populates the required fields
        for a subscription request.
        Returns:
        ----
        {dict} -- The service request with the standard fields filled out.
        """

        # first get the current service request count
        service_count = len(self.data_requests['requests']) + 1

        request = {
            "service": None,
            "requestid": service_count,
            "command": None,
            "account": self.principal_data['accounts'][0]['accountId'],
            "source": self.principal_data['streamerInfo']['appId'],
            "parameters": {
                "keys": None,
                "fields": None
            }
        }

        return request

    def _validate_argument(self, argument: Union[str, int], endpoint: str) -> Union[List[str], str]:
        """Validate field arguments before submitting request.
        Arguments:
        ---
        argument {Union[str, int]} -- Either a single argument or a list of arguments that are
            fields to be requested.

        endpoint {str} -- The subscription service the request will be sent to. For example,
            "level_one_quote".
        Returns:
        ----
        Union[List[str], str] -- The field or fields that have been validated.
        """

        # initalize a new list.
        arg_list = []

        # see if the argument is a list or not.
        if isinstance(argument, list):

            for arg in argument:

                arg_str = str(arg)
                key_list = list(self.fields_ids_dictionary[endpoint].keys())
                val_list = list(self.fields_ids_dictionary[endpoint].values())

                if arg_str in key_list:
                    arg_list.append(arg_str)
                elif arg_str in val_list:
                    key_value = key_list[val_list.index(arg_str)]
                    arg_list.append(key_value)

            return arg_list

        else:

            arg_str = str(argument)
            key_list = list(self.fields_ids_dictionary[endpoint].keys())
            val_list = list(self.fields_ids_dictionary[endpoint].values())

            if arg_str in key_list:
                return arg_str
            elif arg_str in val_list:
                key_value = key_list[val_list.index(arg_str)]
                return key_value

    def quality_of_service(self, qos_level: str) -> None:
        """Quality of Service Subscription.

        Allows the user to set the speed at which they recieve messages
        from the TD Server.
        Arguments:
        ----
        qos_level {str} -- The Quality of Service level that you wish to set.
            Ranges from 0 to 5 where 0 is the fastest and 5 is the slowest.
        Raises:
        ----
        ValueError: Error if no field is passed through.
        Usage:
        ----
            # >>> td_session = TDClient(
            #     client_id='<CLIENT_ID>',
            #     redirect_uri='<REDIRECT_URI>',
            #     credentials_path='<CREDENTIALS_PATH>'
            # )
            # >>> td_session.login()
            # >>> td_stream_session = td_session.create_streaming_session()
            # >>> td_stream_session.quality_of_service(qos_level='express')
            # >>> td_stream_session.stream()
        """
        # valdiate argument.
        qos_level = self._validate_argument(argument=qos_level, endpoint='qos_request')

        if qos_level is not None:

            # Build the request
            request = self._new_request_template()
            request['service'] = 'ADMIN'
            request['command'] = 'QOS'
            request['parameters']['qoslevel'] = qos_level
            self.data_requests['requests'].append(request)

        else:
            raise ValueError('No Quality of Service Level provided.')

    def account_activity(self):
        """
            Represents the ACCOUNT_ACTIVITY endpoint of the TD Streaming API. This service is used to
            request streaming updates for one or more accounts associated with the logged in User ID.
            Common usage would involve issuing the OrderStatus API request to get all transactions
            for an account, and subscribing to ACCT_ACTIVITY to get any updates.
        """

        # Build the request
        request = self._new_request_template()
        request['service'] = 'ACCT_ACTIVITY'
        request['command'] = 'SUBS'
        request['parameters']['keys'] = self.principal_data['streamerSubscriptionKeys']['keys'][0]['key']
        request['parameters']['fields'] = '0,1,2,3'

        self.data_requests['requests'].append(request)

    async def unsubscribe(self, service: str) -> dict:
        """Unsubscribe from a service.
        Arguments:
        ----
        service {str} -- The name of the service, to unsubscribe from. For example,
            "LEVELONE_FUTURES" or "QUOTES".
        Returns:
        ----
        dict -- A message from the websocket specifiying whether the unsubscribe command
            was successful.
        """

        self.unsubscribe_count += 1

        service_count = len(self.data_requests['requests']) + self.unsubscribe_count

        request = {
            "requests": [
                {
                    "service": service.upper(),
                    "requestid": service_count,
                    "command": 'UNSUBS',
                    "account": self.principal_data['accounts'][0]['accountId'],
                    "source": self.principal_data['streamerInfo']['appId']
                }
            ]
        }

        await self._send_message(json.dumps(request))

        return await self._receive_message(return_value=True)

    def close_logic(self, logic_type: str) -> bool:
        """Defines how the stream should close.
        Sets the logic to determine how long to keep the server open.
        If Not specified, Server will remain open forever or until
        it encounters an error.
        Keyword Arguments:
        ----
        logic_type {str} -- Defines what rules to follow to close the conneciton.
            can be either of the following: ['empty', 'market-hours']
        Returns:
        ----
        bool -- Specifiying whether the close logic was set `True`, or
            wasn't set `False`
        """
        pass

    async def close_stream(self) -> None:
        """Closes the connection to the streaming service."""

        # close the connection.
        await self.connection.close()

        # Define the Message.
        message = textwrap.dedent("""
        {lin_brk}
        CLOSING PROCESS INITIATED:
        {lin_brk}
        WebSocket Closed: True
        Event Loop Closed: True
        {lin_brk}
        """).format(lin_brk="=" * 80)

        # Shutdown all asynchronus generators.
        await self.loop.shutdown_asyncgens()

        # Stop the loop.
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop())
            print(message)
            await asyncio.sleep(3)

        # # Once closed, verify it's closed.
        # if self.loop.is_closed():
        #     print('Event loop was closed.')
        # else:
        #     print('Event loop was not closed.')

        # # cancel all the task.
        # for index, task in enumerate(asyncio.Task.all_tasks()):

        #     # let the user know which task is cancelled.
        #     print("Cancelling Task: {}".format(index))

        #     # cancel it.
        #     task.cancel()

        #     try:
        #         await task
        #     except asyncio.CancelledError:
        #         print("main(): cancel_me is cancelled now")


