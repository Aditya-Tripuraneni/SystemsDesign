import hashlib
from typing import List, Dict, Optional
from sortedcontainers import SortedDict

class HashRing: 
    def __init__(self, numVirtualNodes: int = 150):
        self.NUM_VIRTUAL_NODES = numVirtualNodes
        # key: hashval val: node name
        self.ring: SortedDict = SortedDict()

        # map virtual ndoes
        # key: real node val: list of virtual nodes
        self.nodes: Dict[str, List[int]] = {}
    
    def _hash(self, key: str) -> str: 
        hashObject = hashlib.md5(key.encode())

        return int(hashObject.hexdigest()[:8], 16)

    def addNode(self, nodeName: str) -> None: 
        if nodeName in self.nodes: 
            return 
        
        self.nodes[nodeName] = []

        for i in range(self.NUM_VIRTUAL_NODES):
            virtualNode = f"{nodeName}_{i}"
            hashVal = self._hash(virtualNode)
            # this virtual node belongs to this nodename
            self.ring[hashVal] = nodeName

            # track which specific hash belongs to the VN
            self.nodes[nodeName].append(hashVal)
    
    def removeNode(self, nodeName) -> None: 
        if nodeName not in self.nodes:
            return

        virtualNodeHashings = self.nodes[nodeName]
        for hashVal in virtualNodeHashings:
            del self.ring[hashVal]
        
        del self.nodes[nodeName]
    
    def getNode(self, key) -> Optional[str]:
        if not self.ring: 
            return None
    
        hashedKey = self._hash(key)

        hashVals = list(self.ring.keys())

        for ringHash in hashVals: 
            if ringHash >= hashedKey:
                return self.ring[ringHash]
        
        return self.ring[hashVals[0]]

    def getNodes(self, key, numReplicas: int = 1):
        if not self.ring:
            return []

        hashedVal = self._hash(key)
        hashVals = list(self.ring.keys())

        index = None
        for i, ringHash in enumerate(hashVals):
            if ringHash > hashedVal:
                index = i
                break
        
        if index is None: 
            index = 0
        
        reps = []
        seenNodes = set()

        N = len(hashVals)

        for i in range(N):
            currIndex = (index + i) % N
            node = self.ring[hashVals[currIndex]]

            if node not in seenNodes:
                seenNodes.add(node)
                reps.append(node)
            
            if len(reps) == numReplicas:
                break
        
        return reps

    def __repr__(self):
        return f"HashRing(nodes={list(self.nodes.keys())}, ring_size={len(self.ring)})"





ring = HashRing(numVirtualNodes=150)

ring.addNode("Server1")
ring.addNode("Server2")
ring.addNode("Server3")
print(f"Ring: {ring}")

USERS = 1000
keys = [f"User:{i}" for i in range(USERS)]
distribution = {"Server1": 0, "Server2": 0, "Server3": 0}

for key in keys:
    node = ring.getNode(key)
    distribution[node] += 1

print("\nInitial distribution (3 servers, 1000 keys):")
for node, count in sorted(distribution.items()):
    print(f"  {node}: {count} keys ({count/10:.1f}%)")


ring.addNode("Server4")
distribution = {"Server1": 0, "Server2": 0, "Server3": 0, "Server4": 0}

for key in keys: 
    node = ring.getNode(key)
    distribution[node] += 1
print("Distribution after adding server-4:")

for node, count in sorted(distribution.items()):
    print(f"  {node}: {count} keys ({count/10:.1f}%)")

print("\nReplicas for 'user:123' (3 replicas):")
replicas = ring.getNodes("user:123", numReplicas=3)
print(f"  {replicas}")