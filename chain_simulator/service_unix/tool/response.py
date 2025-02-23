from __future__ import annotations
import json
from typing import Dict

class StandardResponse(object):
    code: int = 404
    msg: str = ""
    error: str = ""

    def __init__(self, code: int = 404, msg: str = "", error: str = "") -> None:
        self.code = code
        self.msg = msg
        self.error = error

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
    
    def as_str(self) -> str:
        return json.dumps(self.as_json())
    
    @staticmethod
    def from_str(json_str: str) -> StandardResponse:
        return StandardResponse(**json.loads(json_str))