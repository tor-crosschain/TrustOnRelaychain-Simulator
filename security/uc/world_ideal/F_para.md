### F_pc

```python 

upon receive init(paraid)
    this.id = sid
    cmsgNonce = 0
    cmsgQueue = {}
    cmsgConfirmQueue = {}
    interHeaderQueue = {}
    rootLayer01Queue = {}
    reorgXRootQueue = {}

upon receive createMsg(cData)
    """
    upon receiving cData from Z, F_pc extracts srcappmsg=(srcappid, srcfunc, srcdata) from cData,sends appmsg to related dApp and obtains execution result dstappmsg=(dstappid, dstfunc, dstdata), constructs crossMsg=(this.id, dstid, srcappmsg, dstappmsg, timeoutCmsg), appends crossMsg to merkle tree(R_0) which is only built in current block by reorgMerkleTree function. 
    """
    dstid, dstappid, dstdata = appLayer.execute(srcappid, data)
    cmsg = {srcid: this.id, dstid: dstid, dstappid: dstappid, dstdata: dstdata, height: block.height}
    reorgMerkleTree(block.height, cmsg)
    reply cmsg

upon receive queryXRoot(sid, height)
    return reorgXRootQueue[height]

upon receive queryXRootProof(sid, height, cmsg)
    tree = buildReorgMerkleTree(height)
    proof = getProof(tree, cmsg)
    return proof

upon receive syncInterHeaderToPara(sid, header)
    """
    Protocol:
    upon receiving Hdr_R from R_0, F_pc checks whether Hdr_R exists or not, if it is the case then F_pc call LightClient algorithm of R_0 to verify Hdr_R and store it if verified, else Terminate("verify R_0 header failed")
    """
    hht = header.height
    assert interHeaderQueue[hht] is None
    success = interLightClient.verify(header)
    if not success:
        return
    interHeaderQueue[hht] = header

upon receive storeLayer01ReorgXRoot(sid, interHeight, paraid, paraHeight, rootL01, proofL01):
    """
    upon receiving (interXRHeight, paraHeight, reorgXRoot, interXRMerkleProof) from P_src, F_pc checks: (1) reorgXRoot of XRHeight has not been stored (2) header of XRHeight has been stored in LightClient of R_0. If (1) not satisfied, then Terminates("reorgXRoot has been stored"). If (2) not satisfied, then Terminated("no related R_0 header"). If both are satisfied then F_pc verify reorgXRoot with interXRMerkleProof by merkle tree algorithm of R_0 and store it if verified, else Terminate("verify reorgXRoot failed").
    """
    header = interHeaderQueue[interHeight]
    assert header is not None
    rootQueue = rootLayer01Queue[paraid]
    oldroot = rootQueue[paraHeight]
    if oldroot is not None:
        return oldroot == rootL01
    success = interMerkleAlg.verify(header.stateRoot, rootL01, proofL01)
    if not success:
        return False
    rootLayer01Queue[paraid][paraHeight] = rootL01

upon receive executeLayer02CMsg(sid, paraid, paraHeight, cmsg, proofL02):
    """
    upon receiving (paraid, paraHeight, cmsg, reorgMerkleProof) from P_src, F_pc checks whether reorgXRoot of paraHeight exists, if it exists then F_pc verify cmsg with reorgMerkleProof by merkle tree algorithm of R_0 and execute related dApp if verified. If not exist, F_pc replies Terminate("no related P_src reorgXRoot"). If not verified, then F_pc reply Terminate("verify cmsg failed")
    """
    rootQueue = rootLayer01Queue[paraid]
    rootL01 = rootQueue[paraHeight]
    assert rootL01 is not None
    success = interMerkleAlg.verify(rootL01, cmsg, proofL02)
    if not success:
        return False
    appLayer.execute(cmsg)
```