import asyncio
import hashlib
import struct

from message_codes import MessageCodes
from node import Node
from config.config import dht_config
from loguru import logger


# TODO: in case a bootstrap node leaves, consider the how
#  to handle newly joined nodes (if bootstrap joins back, it doesn't know anyone)
# TODO: change variables to ones in config file
# TODO: SHA-1 conversion
# TODO: ping pong with some frequency (update buckets based on ping pong responses)
#  (in case put/get, add try/catch block, in case of catch rmeove_peer from bucket)
# TODO: extract logic for struct pack and unpack
# TODO: If bucket is full, no need to add to bucket

class Service:
    def __init__(self, node: Node, callback, put_connection, get_connection):
        self.node = node
        self.callback = callback
        self.put_connection = put_connection
        self.get_connection = get_connection



    async def process_message(self, data):
        try:
            # print("data", data)
            # logger.info(f"data {data}")
            size = struct.unpack(">H", data[:2])[0]
            request_type = struct.unpack(">H", data[2:4])[0]
            # print("request_type", request_type)
            logger.info(f"request_type {request_type}")
            # print("size", size)
            logger.info(f"size {size}")
            # print(len(data))
            logger.info(len(data))
            if size == len(data):
                if request_type == MessageCodes.DHT_PING.value:
                    # print("PING ALDIM")
                    logger.info("PING ALDIM")
                    return self.pong_service(data[4:])
                elif request_type == MessageCodes.DHT_PONG.value:
                    # print("PONG ALDIM")
                    logger.info("PONG ALDIM")
                    print(data)
                    # logger.info(data)
                    ip_parts = struct.unpack(">BBBB", data[36:40])
                    ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"
                    listening_port = struct.unpack(">H", data[40:42])[0]
                    self.node.add_peer(self.node.generate_node_id(ip_address, listening_port), ip_address,
                                       listening_port)
                    # print("adding peer with ", ip_address, listening_port)
                    logger.info(f"adding peer with {ip_address}, {listening_port}", )
                    ip_parts = list(map(int, self.node.ip.split('.')))
                    return (struct.pack(">HH", 10, MessageCodes.DHT_FIND_NODE.value) +
                            struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], self.node.port))
                    # return MessageCodes.DHT_FIND_NODE.value

                elif request_type == MessageCodes.DHT_PUT.value:
                    # print("DHT PUT geldim")
                    logger.info("DHT PUT geldim")
                    return await self.put_service(data)
                elif request_type == MessageCodes.DHT_GET.value:
                    # print("DHT GET geldim")
                    logger.info("DHT GET geldim")
                    return await self.get_service(data)
                elif request_type == MessageCodes.DHT_FIND_NODE.value:
                    # print("find_node geldim")
                    logger.info("find_node geldim")
                    return self.find_node_service(data[4:])
                elif request_type == MessageCodes.DHT_NODE_REPLY.value:
                    # print("node reply geldim")
                    logger.info("node reply geldim")
                    # return data
                    nodes_to_connect = self.extract_nodes(data[4:])
                    # print("below printing nodes to connect")
                    logger.info("below printing nodes to connect")
                    for n_c in nodes_to_connect:
                        print(n_c)
                        await asyncio.create_task(self.callback(n_c[0], n_c[1], initiator=True))

                    return "ok".encode()

                elif request_type == MessageCodes.DHT_FIND_VALUE.value:
                    # print("find_value geldim")
                    logger.info("find_value geldim")
                    # return await self.find_value_service(data[4:])
                    return await self.handle_find_value_request(data[4:])

                # elif request_type == MessageCodes.DHT_FOUND_PEERS.value:
                #     print("found_peers geldim")
                #     # return await self.found_peers_service(data[4:])

                elif request_type == MessageCodes.DHT_SUCCESS.value:
                    # print("received success")
                    logger.info("received success")
                    return "get calisti".encode()
                else:
                    # print(f"Invalid request type. Received {request_type}")
                    logger.warning(f"Invalid request type. Received {request_type}")
                    return False
            else:
                # print("WRONG DATA SIZE")
                logger.warning("WRONG DATA SIZE")
        except Exception as e:
            # print("MALFORMED MESSAGE error", e)
            logger.error(f"MALFORMED MESSAGE error {e}")

    # reserved = max_lookup
    # create_task (put a for loop in range alpha) = alpha
    async def put_service(self, data):
        # print("put_service called")
        logger.info("put_service called")
        ttl = int(struct.unpack(">H", data[4:6])[0])
        key = data[8:40]
        value = data[40:]
        replication = int(struct.unpack(">B", data[6:7])[0])
        reserved = int(struct.unpack(">B", data[7:8])[0])
        # print("reserved", reserved)
        logger.info(f"reserved {reserved}")
        # print("key", key)
        # print("value", value)
        logger.info(f"key {key}")
        logger.info(f"value {value}")

        # if key in self.node.storage:
        #     self.node.put(key, value, ttl)


        max_lookup = int(dht_config["max_lookup"])
        if reserved == 0 or reserved > max_lookup:
            reserved = max_lookup

        if reserved == 1:
            self.node.put(key, value, ttl)
            return "put calisti".encode()

        alpha = int(dht_config["alpha"])
        hashed_key = self.get_hashed_key(key)
        closest_nodes = self.node.get_closest_nodes(hashed_key)[:alpha]
        my_distance = self.node.calculate_distance(hashed_key, self.node.id)

        '''
        Replication
        In case I'm closer to key than one nodes from alpha closest, I can store value on myself as well 
        '''
        flag = False
        for c_n in closest_nodes:
            local_distance = self.node.calculate_distance(c_n.id, hashed_key)
            if local_distance > my_distance:
                flag = True

        if flag:
            self.node.put(key, value, ttl)


        # logger.error(f"my distance {self.node.calculate_distance(hashed_key)}")

        reserved -= 1
        for node in closest_nodes:
            logger.info(f"target_node {node}")
            size = 8 + len(key) + len(value)
            msg = struct.pack(">HHHBB", size, MessageCodes.DHT_PUT.value, ttl, replication, reserved) + key + value
            await asyncio.create_task(self.put_connection(node.ip, node.port, msg))

        # logger.info(f"hashed_key {hashed_key}")
        # target_node = self.node.get_closest_nodes(hashed_key)[0]
        #
        # # await self.node.put(hashed_key, value)
        # # print("target_node", target_node)
        # logger.info(f"target_node {target_node}")
        # size = 8 + len(key) + len(value)
        # reserved -= 1
        # msg = struct.pack(">HHHBB", size, MessageCodes.DHT_PUT.value, ttl, replication, reserved) + key + value
        # await asyncio.create_task(self.put_connection(target_node.ip, target_node.port, msg))

        return msg

    async def get_service(self, data):
        key = data[4:]
        # print("dht_key", key)
        logger.info(f"dht_key {key}")
        value = self.node.get(key)
        # print("retrieved value", value)
        logger.info(f"retrieved value {value}")
        if value is not None:
            size = 4 + len(key) + len(value)
            msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + key + value
            # print("returning msg")
            logger.info("returning msg")
            return msg
        else:
            # Start the iterative search
            # print("starting to search")
            logger.info("starting to search")
            result = await self.iterative_find_value(key)

            try:
                request_type = struct.unpack(">H", result[2:4])[0]
                if request_type == MessageCodes.DHT_FAILURE.value:
                    return result
            except Exception as e:
                logger.error(f"error occurred {e}")

            if result is not None:
                # Construct response with the found value

                size = 4 + len(key) + len(result)
                msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + key + result
                return msg
            else:
                # print("result none dondu")
                logger.warning("result = none -- inside get_service else clause")
                return "Value not found".encode()

    # async def iterative_find_value(self, key, queried_nodes=set(), new_closest_nodes=[]):
    #     # Start the search with closest nodes
    #     hashed_key = self.get_hashed_key(key)
    #     closest_nodes = self.node.get_closest_nodes(hashed_key)[:3]
    #     # print("closest nodes", closest_nodes)
    #     closest_nodes = closest_nodes + new_closest_nodes
    #     logger.info(f"closest nodes {closest_nodes}")
    #     for node in closest_nodes:
    #         if (node.ip, node.port) not in queried_nodes:
    #             # Query this node
    #             # print("sending query_node_for_value for ", node.ip, node.port)
    #             logger.info(f"sending query_node_for_value for {node.ip}, {node.port}")
    #             response = await self.query_node_for_value(node, key)
    #
    #             # Check if the value was returned
    #             if 'value' in response:
    #                 # print("returning value from iterative_find_value", response['value'])
    #                 logger.info(f"returning value from iterative_find_value {response['value']}")
    #                 return response['value']
    #             else:
    #                 # Add this node to queried nodes and continue the search
    #                 queried_nodes.add((node.ip, node.port))
    #                 new_closest_nodes = response.get('closest_nodes', [])
    #
    #                 # print("iterative_find_value else clause")
    #                 logger.info("iterative_find_value else clause")
    #                 # Query the new closest nodes
    #                 for new_node in new_closest_nodes:
    #                     logger.info("iterative_find_value else clause for loop inside")
    #                     result = await self.iterative_find_value(key, queried_nodes, new_closest_nodes)
    #                     if result is not None:
    #                         return result
    #
    #     size = 4 + len(key)
    #     msg = struct.pack(">HH", size, MessageCodes.DHT_FAILURE.value) + key
    #     return msg  # Value not found

    async def iterative_find_value(self, key):
        hashed_key = self.get_hashed_key(key)
        closest_nodes = self.node.get_closest_nodes(hashed_key)[:3]
        closest_nodes = closest_nodes[::-1]
        logger.info(f"closest nodes {closest_nodes}")
        queried_nodes = set()
        queried_nodes.add((self.node.ip, self.node.port))

        nodes_to_query = asyncio.LifoQueue()
        for node in closest_nodes:
            await nodes_to_query.put(node)

        while not nodes_to_query.empty():
            node = await nodes_to_query.get()
            logger.info(f"nodes to query {nodes_to_query}")

            logger.info(f"queue size {nodes_to_query.qsize()}")
            print("node = await nodes_to_query.get() - ", node)
            print("queried_nodes", queried_nodes)
            if (node.ip, node.port) in queried_nodes:
                continue  # skip nodes that have already been queried

            logger.info("on line 234")
            queried_nodes.add((node.ip, node.port))
            response = await self.query_node_for_value(node, key)

            if 'value' in response:
                logger.info(f"returning value from iterative_find_value {response['value']}")
                return response['value']

            new_closest_nodes = response.get('closest_nodes', [])
            new_closest_nodes = new_closest_nodes[::-1] # reverse
            print("new_closest_nodes", new_closest_nodes)
            for new_node in new_closest_nodes:
                logger.info("iterative_find_value new_node in new_closest_nodes")
                await nodes_to_query.put(new_node)

        size = 4 + len(key)
        msg = struct.pack(">HH", size, MessageCodes.DHT_FAILURE.value) + key
        return msg  # Value not found

    async def query_node_for_value(self, node, key):
        # Send a find_value request to the given node
        # print("trying to query node", node.ip, node.port)
        logger.info(f"trying to query node {node.ip}, {node.port}")
        size = 4 + len(key)
        msg = struct.pack(">HH", size, MessageCodes.DHT_FIND_VALUE.value) + key
        reader, writer = await asyncio.open_connection(node.ip, node.port)

        try:
            # Send the message
            writer.write(msg)
            await writer.drain()

            # Read the response
            # print("reading before reader")
            logger.info("reading before reader")
            data = await reader.read(1000)  # Adjust the byte count as necessary
            request_type = struct.unpack(">H", data[2:4])[0]
            # print("reading after reader")
            logger.info("reading after reader")

            if request_type == MessageCodes.DHT_SUCCESS.value:
                value = data[36:]  # Adjust as per actual format
                # print("return value from query_node_for_value")
                logger.info("return value from query_node_for_value")
                return {"value": value}
            elif request_type == MessageCodes.DHT_NODE_REPLY.value:
                nodes_list = self.extract_nodes_found_peers(data[4:])
                return {"closest_nodes": nodes_list}
            else:
                # Handle other response types or errors as needed
                logger.error("Invalid response type or error in communication")
                return {"error": "Invalid response type or error in communication"}

        finally:
            # Close the connection
            writer.close()
            await writer.wait_closed()

    # try:
    #     # Read response
    #     print("reading before reader")
    #     data = await reader.read(100)  # Adjust buffer size as needed
    #     request_type = struct.unpack(">H", data[2:4])[0]
    #     print("reading after reader")
    #
    #     if request_type == MessageCodes.DHT_SUCCESS.value:
    #         value = data[4:]  # Adjust as per actual format
    #         print("return value from query_node_for_value")
    #         return {"value": value}
    #     elif request_type == MessageCodes.DHT_NODE_REPLY.value:
    #         nodes_list = self.extract_nodes(data[4:])
    #         return {"closest_nodes": nodes_list}
    #     else:
    #         # Handle other response types or errors as needed
    #         return {"error": "Invalid response type or error in communication"}
    #
    # finally:
    #     writer.close()
    #     await writer.wait_closed()

    async def handle_find_value_request(self, key):
        # Check if this node holds the value for the given key
        print("handle_find_value_request geldim")
        # logger.info("handle_find_value_request geldim")
        value = self.node.get(
            key)  # Assuming this function retrieves the value for the given key from the node's local store

        if value:
            # Return the value if it exists
            response = struct.pack(">HH", len(key) + len(value) + 4, MessageCodes.DHT_SUCCESS.value) + key + value
            return response

        else:
            print("handle_find_value_request else clause girdim")
            # logger.info("handle_find_value_request else clause girdim")
            # If the node doesn't have the value, find the k closest nodes to the key
            hashed_key = self.get_hashed_key(key)
            closest_nodes = self.node.get_closest_nodes(hashed_key)[:3]
            print("handle_find_value_request else clause success entry")
            # logger.info("handle_find_value_request else clause success entry")
            header = struct.pack(">HHH", 6 + len(closest_nodes) * 6, MessageCodes.DHT_NODE_REPLY.value,
                                 len(closest_nodes))
            packed_nodes = b''
            for n in closest_nodes:
                print("inner node", n)
                # logger.info(f"inner node {n}")
                # pack each node
                ip_parts = [int(part) for part in n.ip.split('.')]

                node_data = struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], n.port)
                packed_nodes += node_data

            # combine header and nodes
            node_reply = header + packed_nodes
            print("local size", struct.unpack(">H", node_reply[:2])[0])
            print("handle_find_value_request else clause success exit")

            return node_reply

    # 01      20
    # 20      40
    # 40      60

    # async def get_service(self, data):
    #     dht_key = data[4:]
    #     print("dht_key", dht_key)
    #     value = self.node.get(dht_key)
    #     print("retrieved value", value)
    #     if value is not None:
    #         size = 4 + len(dht_key) + len(value)
    #         msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + dht_key + value
    #         print("returning msg")
    #         return msg
    #     else:
    #         # print("sending to closest 3 nodes")
    #         # hashed_key = self.get_hashed_key(dht_key)
    #         # target_node = self.node.get_closest_nodes(hashed_key)
    #         # if len(target_node) >= 3:
    #         #     for i in range(0, 3):
    #         #         print("sending to", target_node[i].ip, target_node[i].port)
    #         #         reader, writer = await asyncio.open_connection(target_node[i].ip, target_node[i].port)
    #         #         size = 4 + len(dht_key)
    #         #         msg = struct.pack(">HH", size, MessageCodes.DHT_FIND_VALUE.value) + dht_key
    #         #         writer.write(msg)
    #         #         await writer.drain()
    #         #
    #         #         # Read response
    #         #         data = await reader.read(100)  # Adjust buffer size as needed
    #         #         request_type = struct.unpack(">H", data[2:4])[0]
    #         #         if request_type == MessageCodes.DHT_SUCCESS:
    #         #             return data
    #         #         i = 5
    #         #         while request_type != MessageCodes.DHT_SUCCESS.value:
    #         #             nodes_to_connect = self.extract_nodes(data[4:])
    #         #             for n_c in nodes_to_connect:
    #         #                 print(n_c)
    #         #                 await asyncio.create_task(self.callback(n_c[0], n_c[1], initiator=True))
    #         #
    #         #         writer.close()
    #         #         await writer.wait_closed()
    #         # return await self.find_value_service(dht_key)
    #         # Get the closest 3 nodes based on the key
    #
    #
    #         return "get calisti".encode()

    # async def find_value_service(self, data):
    #     dht_key = data
    #     value = self.node.get(dht_key)
    #     print("retrieved value", value)
    #     print("inside find_value_service")
    #     if value is not None:
    #         print("successful find_value_service")
    #         print(self.node.ip, self.node.port)
    #         size = 4 + len(dht_key) + len(value)
    #         msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + dht_key + value
    #         print("returning msg")
    #         return msg
    #     else:
    #         print("else part of find_value_service")
    #         hashed_key = self.get_hashed_key(dht_key)
    #         target_node = self.node.get_closest_nodes(hashed_key)
    #         closest_nodes = target_node[:3]   # Get 3 peers
    #
    #         header = struct.pack(">HHH", 6 + len(closest_nodes) * 6, MessageCodes.DHT_FOUND_PEERS.value,
    #                              len(closest_nodes))
    #         packed_nodes = b''
    #         for n in closest_nodes:
    #             print("inner node", n)
    #             # pack each node
    #             ip_parts = [int(part) for part in n.ip.split('.')]
    #             # packed_ip = struct.pack(">BBBB", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3])
    #
    #             node_data = struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], n.port)
    #             packed_nodes += node_data
    #
    #         # combine header and nodes
    #         found_peers = header + packed_nodes
    #         print("local size", struct.unpack(">H", found_peers[:2])[0])
    #
    #
    #         return found_peers

    # ---------------------------------------------------------------------------------------------------------------

    # async def get_service(self, data):
    #     dht_key = data[4:]
    #     print("dht_key", dht_key)
    #     value = self.node.get(dht_key)
    #     print("retrieved value", value)
    #     if value is not None:
    #         size = 4 + len(dht_key) + len(value)
    #         msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + dht_key + value
    #         print("returning msg")
    #         return msg
    #     else:
    #         print("sending to closest 3 nodes")
    #         hashed_key = self.get_hashed_key(dht_key)
    #         target_node = self.node.get_closest_nodes(hashed_key)
    #         if len(target_node) >= 3:
    #             tasks = []
    #             for i in range(0, 3):
    #                 print("sending to", target_node[i].ip, target_node[i].port)
    #                 size = 4 + len(dht_key)
    #                 msg = struct.pack(">HH", size, MessageCodes.DHT_FIND_VALUE.value) + dht_key
    #                 task = asyncio.create_task(self.get_connection(target_node[i].ip, target_node[i].port, msg))
    #                 tasks.append(task)
    #                 print("found_peers", task)
    #             something = await asyncio.gather(*tasks)
    #             print("something", something)
    #     return "get calisti".encode()

    # async def find_value_service(self, data):
    #     dht_key = data
    #     value = self.node.get(dht_key)
    #     print("retrieved value", value)
    #     print("inside find_value_service")
    #     if value is not None:
    #         print("successful find_value_service")
    #         print(self.node.ip, self.node.port)
    #         size = 4 + len(dht_key) + len(value)
    #         msg = struct.pack(">HH", size, MessageCodes.DHT_SUCCESS.value) + dht_key + value
    #         print("returning msg")
    #         return msg
    #     else:
    #         print("else part of find_value_service")
    #         hashed_key = self.get_hashed_key(dht_key)
    #         target_node = self.node.get_closest_nodes(hashed_key)
    #         return target_node[:3]
    #
    # async def found_peers_service(self, data):
    #     pass

    def ping_service(self):
        unique_str = f"{self.node.ip}:{self.node.port}"
        ip_parts = list(map(int, self.node.ip.split('.')))
        message = (struct.pack(">HH", 42, MessageCodes.DHT_PING.value) +
                   hashlib.sha256(unique_str.encode()).digest() +
                   struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], self.node.port))
        print("sending ping message")
        return message

    def pong_service(self, data):
        node_id = data[0:32]
        integer_representation = int.from_bytes(node_id, 'big')
        print(integer_representation)
        ip_parts = struct.unpack(">BBBB", data[32:36])
        ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"
        listening_port = struct.unpack(">H", data[36:38])[0]

        print(ip_address, listening_port)
        self.node.add_peer(integer_representation, ip_address, listening_port)
        ip_parts = list(map(int, self.node.ip.split('.')))

        return (struct.pack(">HH", 42, MessageCodes.DHT_PONG.value) +
                node_id +
                struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], self.node.port))

    def find_node_service(self, data):
        print("find_node_service called")
        ip_parts = struct.unpack(">BBBB", data[0:4])
        ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"
        port = struct.unpack(">H", data[4:6])[0]
        print(ip_address, port)

        node_id = self.node.generate_node_id(ip_address, port)
        closest_nodes = self.node.get_closest_nodes(node_id)

        closest_nodes = self.filter_nodes(closest_nodes, node_id)
        """
        2 - size
        2 - message type
        2 - number of nodes
        len(closest_nodes) * 6 (ip, port) - Nodes
        """
        header = struct.pack(">HHH", 6 + len(closest_nodes) * 6, MessageCodes.DHT_NODE_REPLY.value, len(closest_nodes))
        packed_nodes = b''
        for n in closest_nodes:
            print("inner node", n)
            # pack each node
            ip_parts = [int(part) for part in n.ip.split('.')]
            # packed_ip = struct.pack(">BBBB", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3])

            node_data = struct.pack(">BBBBH", ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], n.port)
            packed_nodes += node_data

        # combine header and nodes
        node_reply = header + packed_nodes
        print("local size", struct.unpack(">H", node_reply[:2])[0])
        return node_reply

        # return "finding node"

    def extract_nodes(self, data):
        num_nodes = struct.unpack(">H", data[:2])[0]
        print("num_nodes", num_nodes)
        nodes_to_connect = []
        prev, next = 2, 8

        for i in range(num_nodes):
            ip_parts = struct.unpack(">BBBB", data[prev:(next - 2)])
            ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"
            port = struct.unpack(">H", data[(next - 2):next])[0]
            print("ip_address", ip_address)
            print("port", port)
            prev = next
            next += 6
            nodes_to_connect.append((ip_address, port))

        nodes_to_connect = self.filter_nodes_1(nodes_to_connect)

        return nodes_to_connect

    def extract_nodes_found_peers(self, data):
        num_nodes = struct.unpack(">H", data[:2])[0]
        print("num_nodes", num_nodes)
        nodes_to_connect = []
        prev, next = 2, 8

        for i in range(num_nodes):
            ip_parts = struct.unpack(">BBBB", data[prev:(next - 2)])
            ip_address = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"
            port = struct.unpack(">H", data[(next - 2):next])[0]
            print("ip_address", ip_address)
            print("port", port)
            prev = next
            next += 6
            nodes_to_connect.append(
                Node(
                     ip=ip_address,
                     port=port
                )
            )

        return nodes_to_connect

    def filter_nodes(self, closest_nodes, node_id):
        print("to remove", node_id)
        return [node for node in closest_nodes if node.id != node_id and node not in self.node.k_buckets]

    def filter_nodes_1(self, nodes):
        print("my k bucket")

        k_bucket_nodes = set()

        for bucket in self.node.k_buckets:
            for node in bucket.nodes:
                k_bucket_nodes.add((node.ip, node.port))
                print(node)

        # Use a list comprehension to filter out any nodes that are in the k_bucket_nodes set
        # filtered_nodes = [node for node in nodes if node not in k_bucket_nodes]
        filtered_nodes = []
        for n in nodes:
            if n not in k_bucket_nodes:
                filtered_nodes.append(n)

        return filtered_nodes

    @staticmethod
    def get_hashed_key(key):
        return int(hashlib.sha256(key).hexdigest(), 16)
