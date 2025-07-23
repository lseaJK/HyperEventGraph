# src/event_extraction/base_extractor.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type
from .schemas import BaseEvent

class BaseEventExtractor(ABC):
    """
    事件抽取器的抽象基类。
    定义了所有具体抽取器必须实现的通用接口。
    """

    @abstractmethod
    async def extract(
        self,
        text: str,
        event_model: Type[BaseEvent],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseEvent]:
        """
        从文本中抽取单个结构化事件。

        Args:
            text (str): 需要从中抽取事件的输入文本。
            event_model (Type[BaseEvent]): 用于指导抽取的Pydantic事件模型。
            metadata (Optional[Dict[str, Any]]): 包含额外上下文的元数据，
                                                 例如文档ID或来源信息。

        Returns:
            Optional[BaseEvent]: 一个填充了抽取数据的Pydantic事件模型实例，
                                 如果无法抽取有效事件，则返回None。
        """
        pass

    async def batch_extract(
        self,
        texts: List[str],
        event_model: Type[BaseEvent],
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[Optional[BaseEvent]]:
        """
        从文本列表中批量抽取事件。
        默认实现是循环调用单个抽取方法，子类可以重写以实现更高效的批量处理。

        Args:
            texts (List[str]): 需要从中抽取事件的输入文本列表。
            event_model (Type[BaseEvent]): 用于指导抽取的Pydantic事件模型。
            metadata_list (Optional[List[Dict[str, Any]]]): 每个文本对应的元数据列表。

        Returns:
            List[Optional[BaseEvent]]: 与输入文本列表对应的Pydantic事件模型实例列表。
        """
        if metadata_list and len(texts) != len(metadata_list):
            raise ValueError("texts 和 metadata_list 的长度必须一致。")

        tasks = []
        for i, text in enumerate(texts):
            metadata = metadata_list[i] if metadata_list else None
            tasks.append(self.extract(text, event_model, metadata))
        
        return await asyncio.gather(*tasks)

    def get_supported_event_types(self) -> List[str]:
        """
        返回此抽取器明确支持的事件类型名称列表。
        如果抽取器是通用的，可以返回一个空列表。

        Returns:
            List[str]: 支持的事件类型名称列表。
        """
        return []
