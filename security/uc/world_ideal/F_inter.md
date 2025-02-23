### F_ic
```python
upon receive init(interid)
    this.id = interid
    paraHeaderQueue = {}
    paraReorgRootQueue = {}
    paraLightClients = {}
    paraMerkleAlgs = {}

upon receive syncParaHeaderToInter(sid, paraid, header)
    """
    Protocol:
    upon receiving Hdr_src from P_src, F_ic checks whether Hdr_src exists or not, if it is the case then F_ic call LightClient algorithm of P_src to verify Hdr_src and store it if verified, else Terminate("verify P_src header failed")
    """
    hht = header.height
    paraHeaders = paraHeaderQueue[paraid]
    if paraHeaders is None:
        paraHeaders[hht] = header
    else:
        assert paraHeaders[hht] is None
        lastHeader = paraHeaders[hht-1]
        assert lastHeader is not None
        lightClient = paraLightClients[paraid]
        success = lightClient.verify(lastHeader, header)
        if not success:
            return False
        paraHeaders[hht] = header
    paraHeaderQueue[paraid] = paraHeaders

upon receive syncReorgXRoot(sid, paraid, height, reorgRoot, paraMerkleproof)
    """
    upon receiving (paraid, XRHeight, reorgXRoot, paraXRootMP) from P_src, F_ic checks: (1) reorgXRoot of XRHeight has not been stored (2) header of XRHeight has been stored in LightClient of P_src. If (1) not satisfied, then Terminates("reorgXRoot has been stored"). If (2) not satisfied, then Terminated("no related P_src header"). If both are satisfied then F_ic verify reorgXRoot with paraXRootMP by merkle tree algorithm of P_src and store it if verified, else Terminated("verify reorgXRoot failed").
    """
    reorgRoots = paraReorgRootQueue[paraid]
    oldRoot = reorgRoots[height]
    if oldRoot is not None:
        return reorgRoots[height] == reorgRoot
    else:
        header = paraHeaderQueue[paraid][height]
        assert header is not None
        merkleAlg = paraMerkleAlgs[paraid]
        success = merkleAlg.verify(header, reorgRoot, proof)
        if not success:
            return False
        reorgRoots[height] = reorgRoot
        paraReorgRootQueue[paraid] = reorgRoots
        return True
```