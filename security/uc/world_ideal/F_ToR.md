### F_ToR

```python


upon receive setup(ID_src, ID_dst)
    assert ID_src != ID_dst
    P_src.id = ID_src
    P_dst.id = ID_dst
    deploy CSC_src on P_src with ID_src
    deploy CSC_dst on P_dst with ID_dst
    generate unique session identifier S_id
    sessions[S_id] = {srcid: P_src.id, dstid:P_dst.id, csrc: CSC_src, cdst: CSC_dst, state: STARTED}
    set timeoutInter
    set timeoutDst
    rHSmt = {} # {height_of_inter_header: bool_submit_to_P_dst}
    rHCfm = {} # {height_of_inter_header: bool_confirm_on_P_dst}
    pHSmt = {} # {height_of_para_header: bool_submit_to_R_0}
    pXRSmt = {} # {height_of_para_XRoot: bool_submit_to_R_0}
    pXRCfm = {} # {height_of_para_XRoot: height_confirmed_on_R_0, default 0}

upon receive paraHeader(sid, paraid, header)
    """
    Protocol:
    upon receiving Hdr_src from P_src, F_ToR construct transaction TX_PH2R={P_src.id, Hdr_src}, submit it to R_0 and set pHSmt[Hdr_src.height]=True. 
    upon receiving (reorgXRoot, paraXRootMP, XRHeight) from P_src, if pHSmt[XRHeight] is True, F_ToR construct transaction TX_XRtI={P_src.id, XRHeight, reorgXRoot, paraXRootMP}, submit it to R_0 and set pXRSmt[XRHeight]=True, pXRCfm[XRHeight]=0.
    """
    session = sessions[sid]
    assert session is not None
    assert paraid == session.srcid
    # submit para header to inter
    construct TX_PHtI = {paraid, header}
    leak TX_PHtI
    submit TX_PHtI to R_0_csc
    query reorgXRoot of height=xHeight on P_src_csc
    query paraMerkleProof of reorgXRoot on P_src
    construct TX_XRtI = {paraid, xHeight, reorgXRoot, paraMerkleproof}
    leak TX_XRtI
    submit TX_XRtI to R_0_csc    

upon receive interHeader(sid, header)
    """
    Protocol:
    upon receiving Hdr_R from R_0, F_ToR construct transaction TX_IHtP={Hdr_R}, submit it to P_dst and set rHSmt[Hdr_R.height] = True
    """
    construct TX_IHtP = {header}
    submit TX_IHtP to P_dst_csc

upon receive crossMsg(sid, paraid, paraHeight, cmsg)
    """
    Protocol:
    upon receiving receipt_XR of transaction TX_XRtI from R_0, set pXRCfm[XRHeight] = receipt_XR.height, 
    upon receiving receipt_Hdr_R of transaction TX_IHtP from P_dst, set rHCfm[Hdr_R.height] = True

    upon receiving {interXRHeight, XRHeight, reorgXRoot, interXRMerkleProof} from P_src, if rHCfm[interXRHeight] = True, then F_ToR constructs transaction TX_setL01XRoot={interXRHeight, XRHeight, reorgXRoot, interXRMerkleProof} and submit it to P_dst, set rXRsmt[XRHeight]=True, else F_ToR terminates.

    upon receiving (crossMsg, cmHeight, reorgMerkleProof) from P_src, if rXRsmt[cmHeight] = True, then F_ToR constructs transaction TX_execL02CMsg={crossMsg, cmHeight, reorgMerkleProof} and submits it to P_dst, else F_ToR terminates
    """
    session = sessions[sid]
    assert session is not None
    assert cmsg.srcid == session.srcid
    assert cmsg.dstid == session.dstid
    # wait reorgXRoot on inter chain
    wait reorgXRoot of height=paraHeight is confirmed on R_0 for timeoutInter
    query interXRHeight of reorgXRoot confirmed on R_0
    wait header of height=XRHeight is confirmed on P_dst for timeoutDst
    query reorgXRoot of height=paraheight on R_0_csc
    query interXRMerkleProof of reorgXRoot on R_0
    # Layer01
    query reorgXRoot exists on P_dst_csc
    if not exists:
        construct TX_setL01XRoot = {interXRHeight, paraid, paraHeight, reorgXRoot, interXRMerkleProof}
        submit TX_setL01XRoot to P_dst_csc
    # Layer02
    query reorgMerkleProof of cmsg on P_src_csc
    construct TX_executeLayer02CMsg = {paraid, paraHeight, cmsg, reorgMerkleProof}
    submit TX_executeLayer02CMsg to P_dst_csc

upon receive createMsg(**)
    pass
```