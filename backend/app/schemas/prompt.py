from typing import Optional

from pydantic import BaseModel, Field


class PromptBase(BaseModel):
    """Prompt 基础模型。"""

    name: str = Field(..., description="唯一标识，用于代码引用")
    title: Optional[str] = Field(default=None, description="可读标题")
    content: str = Field(..., description="提示词具体内容")


class PromptCreate(PromptBase):
    """创建 Prompt 时使用的模型。"""

    pass


class PromptUpdate(BaseModel):
    """更新 Prompt 时使用的模型。"""

    title: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)


class PromptRead(PromptBase):
    """对外暴露的 Prompt 数据结构。"""

    id: int

    class Config:
        from_attributes = True
