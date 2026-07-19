from pydantic import BaseModel,Field
# 定义数据结构，自动校验数据，转换和序列化数据,帮助生成接口文档
class TripPreviewRequest(BaseModel):
      origin: str = Field(min_length=1,max_length=50)
      destination: str = Field(min_length=1 ,max_length=50)


class TripPreviewResponse(BaseModel):
    message: str