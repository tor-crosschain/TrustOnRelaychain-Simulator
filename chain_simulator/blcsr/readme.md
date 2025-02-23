# algorithm description

```python
def update(height: int, cm: str):
    """
    Update Merkle root by adding a new leaf node
    time complexity: O(logN)
    storage complexity: O(logN)
    """

    # ---- init ----
    (_, path, index) = blockMerkle[height]
    index += 1
    tempnode = sha(cm)
    nextpaths = []
    # UNSET: uninitialized
    # ALLEVEN: no odd-positioned nodes in the path (only even-positioned nodes exist)
    # ODD: odd-positioned nodes exist in the path
    flag = UNSET
    pathpoint = 0
    # --------------

    while index >= 1:
        if index == 1:
            root = tempnode
            nextpaths.append(tempnode)
            break
        if odd(index):
            # If current node is odd
            if flag in [UNSET, ALLEVEN]:
                # If current node is a leaf node (flag=-1), then current node belongs to the generation path of the right neighboring leaf node
                # If current node is not a leaf node, and all nodes from leaf to current are even-positioned, indicating the subtree rooted at current node is a perfect binary tree,
                # then current node belongs to the generation path of any leaf node in the right neighboring subtree
                nextpaths.append(tempnode)
            tempnode = sha(tempnode+tempnode)
            flag = 1 # Current node is odd-positioned, set flag=1
            index = math.ceil(index/2) # Traverse up to parent node
        else:
            # If current node is even, it needs to compute hash with its left neighbor
            node = path[pathpoint]
            pathpoint += 1
            if flag == ODD:
                # If there exists odd-positioned nodes in the path from leaf to current node,
                # indicating the subtree rooted at current node is not yet a complete binary tree,
                # then the left neighbor belongs to the generation path of all leaf nodes in the subtree rooted at current node
                nextpaths.append(node)
            if flag == UNSET:
                # If flag is not initialized, since current node is even-positioned, set flag=0
                # If flag == 1, even though current node is even-positioned, according to flag definition, we cannot set flag=0
                flag = 0
            tempnode = sha(node+tempnode)
            index = math.ceil(index/2) # Traverse up to parent node
    blockMerkle[height] = (root, nextpaths, index)
```