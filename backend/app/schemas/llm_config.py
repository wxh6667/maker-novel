from typing import Optional

from pydantic import BaseModel, Field


# ============ Provider 管理相关 Schema ============

class ProviderCreate(BaseModel):
    """创建/更新 Provider 请求。"""
    name: str = Field(..., description="Provider 名称（唯一标识）")
    model: str = Field(..., description="模型名称")
    provider: Optional[str] = Field(default="openai_compat", description="Provider 类型")
    base_url: Optional[str] = Field(default=None, description="API Base URL")
    api_key: Optional[str] = Field(default=None, description="API Key")
    temperature: Optional[float] = Field(default=0.5, ge=0, le=2, description="温度参数")
    max_tokens: Optional[int] = Field(default=4096, ge=1, description="最大 Token 数")
    timeout: Optional[float] = Field(default=300.0, ge=1, description="超时时间(秒)")
    support_json_mode: Optional[bool] = Field(default=True, description="是否支持 JSON 模式输出")
    support_stream: Optional[bool] = Field(default=True, description="是否支持流式输出")
    proxy: Optional[str] = Field(default=None, description="代理地址，如 socks5://host:port")
    embed_api_type: Optional[str] = Field(default="openai", description="Embedding API 类型: openai / gemini")


class ProviderRead(BaseModel):
    """Provider 配置响应（不含敏感信息）。"""
    name: str = Field(..., description="Provider 名称")
    model: str = Field(..., description="模型名称")
    provider: Optional[str] = Field(default=None, description="Provider 类型")
    base_url: Optional[str] = Field(default=None, description="API Base URL")
    temperature: Optional[float] = Field(default=None, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, description="最大 Token 数")
    timeout: Optional[float] = Field(default=None, description="超时时间(秒)")
    has_api_key: bool = Field(default=False, description="是否已配置 API Key")
    support_json_mode: Optional[bool] = Field(default=True, description="是否支持 JSON 模式输出")
    support_stream: Optional[bool] = Field(default=True, description="是否支持流式输出")
    proxy: Optional[str] = Field(default=None, description="代理地址")
    embed_api_type: Optional[str] = Field(default="openai", description="Embedding API 类型")


class ProviderListResponse(BaseModel):
    """Provider 列表响应。"""
    providers: list[ProviderRead] = Field(default_factory=list, description="Provider 列表")
