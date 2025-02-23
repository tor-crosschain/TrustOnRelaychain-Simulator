from __future__ import annotations
import json
from typing import Dict


class StandardResponse(object):
    code: int = 199
    msg: str = ""
    error: str = ""

    def __init__(self) -> None:
        pass

    def set_code(self, code: int) -> StandardResponse:
        self.code = code
        return self

    def set_msg(self, msg: str) -> StandardResponse:
        self.msg = msg
        return self

    def set_error(self, err: str) -> StandardResponse:
        self.error = err
        return self

    def as_json(self) -> Dict:
        return {"code": self.code, "msg": self.msg, "error": self.error}
