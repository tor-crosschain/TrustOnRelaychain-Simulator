import hashlib
import math


sha = lambda x: hashlib.sha256(str(x).encode()).hexdigest()
odd = lambda x: bool(x % 2)
ceillog = lambda x: 2 ** math.ceil(math.log(x, 2))


def update(path: list, index: int, cm: str):
    """
    Update Merkle root by adding new leaf node
    time complexity: O(logN)
    storage complexity: O(logN)
    """
    tempnode = sha(cm)
    nextpaths = []
    flag = -1  # -1: uninitialized; 0: no odd position nodes on path (only even position nodes); 1: odd position nodes exist on path
    pathpoint = 0
    while index >= 1:
        if index == 1:
            root = tempnode
            nextpaths.append(tempnode)
            break
        if odd(index):
            # If current node is odd
            if flag in [-1, 0]:
                # If current node is leaf node (flag=-1), then current node belongs to right neighbor leaf node's generation path
                # If current node is not leaf node, and all nodes from leaf to here are even nodes, indicating subtree rooted at current node is perfect binary tree,
                # then current node belongs to generation path of any leaf node in right neighbor subtree
                nextpaths.append(tempnode)
            tempnode = sha(tempnode + tempnode)
            flag = 1  # Current node is odd, set flag=1
            index = math.ceil(index / 2)  # Traverse up to parent node
        else:
            # If current node is even, then current node needs to calculate hash with left neighbor node
            node = path[pathpoint]
            pathpoint += 1
            if flag == 1:
                # If odd nodes exist in nodes from leaf up to here, indicating subtree rooted at current node is not yet complete binary tree,
                # then left neighbor node belongs to generation path of all leaf nodes in subtree rooted at current node
                nextpaths.append(node)
            if flag == -1:
                # If flag is not initialized, then because current node is even position node, set flag=0
                # If flag == 1, then even if current node is even position node, according to flag definition, cannot set flag=0
                flag = 0
            tempnode = sha(node + tempnode)
            index = math.ceil(index / 2)  # Traverse up to parent node
    return root, nextpaths


def merkletree(cms: list) -> str:
    length = len(cms)
    if length == 0:
        return None
    l = ceillog(length)
    if l == 1:
        if cms[0] is None:
            return None
        return sha(cms[0])
    cms += [None for i in range(l - length)]
    mid = l // 2
    left = merkletree(cms[:mid])
    right = merkletree(cms[mid:]) or left
    if right is None:
        return None
    # print(left+right)
    return sha(left + right)


if __name__ == "__main__":
    cms = [str(x) for x in range(8)]
    mkroots = []
    for i in range(1, len(cms) + 1):
        root = merkletree(cms[:i])
        mkroots.append(root)
    # print(*mkroots)
    print("---------------update---------------")
    path = []
    updateroots = []
    for idx, cm in enumerate(cms):
        print(path)
        root, path = update(path, idx + 1, cm)
        updateroots.append(path[-1])
    # print(*updateroots)
    print(all(x[0] == x[1] for x in zip(mkroots, updateroots)))
