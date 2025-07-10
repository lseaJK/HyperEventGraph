import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path

# 导入自定义模块
from deepseek_extractor import DeepSeekEventExtractor
from deepseek_config import DeepSeekConfig, get_config
from validation import EventExtractionValidator, ValidationResult
from prompt_templates import PromptTemplateGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventExtractionService:
    """
    事件抽取服务主类
    集成DeepSeek模型、验证器和模板生成器
    """
    
    def __init__(self, 
                 config_name: str = "default",
                 custom_config: Optional[Dict[str, Any]] = None,
                 enable_validation: bool = True,
                 enable_logging: bool = True):
        """
        初始化事件抽取服务
        
        Args:
            config_name: 配置名称
            custom_config: 自定义配置
            enable_validation: 是否启用验证
            enable_logging: 是否启用日志
        """
        self.enable_validation = enable_validation
        self.enable_logging = enable_logging
        
        # 初始化配置
        if custom_config:
            self.config = DeepSeekConfig.from_dict(custom_config)
        else:
            self.config = get_config(config_name)
        
        # 初始化组件
        self.extractor = None
        self.validator = None
        self.template_generator = None
        
        # 统计信息
        self.stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "start_time": datetime.now()
        }
        
        logger.info(f"事件抽取服务初始化完成，配置: {config_name}")
    
    async def initialize(self):
        """
        异步初始化所有组件
        """
        try:
            # 初始化DeepSeek抽取器
            self.extractor = DeepSeekEventExtractor(config=self.config)
            logger.info("DeepSeek事件抽取器初始化成功")
            
            # 初始化验证器
            if self.enable_validation:
                self.validator = EventExtractionValidator()
                logger.info("事件验证器初始化成功")
            
            # 初始化模板生成器
            self.template_generator = PromptTemplateGenerator()
            logger.info("Prompt模板生成器初始化成功")
            
            # 验证配置
            self.config.validate_config()
            logger.info("配置验证通过")
            
            return True
            
        except Exception as e:
            logger.error(f"服务初始化失败: {str(e)}")
            raise
    
    async def extract_single_event(self,
                                 text: str,
                                 domain: str,
                                 event_type: str,
                                 metadata: Optional[Dict[str, Any]] = None,
                                 validate_result: bool = None) -> Dict[str, Any]:
        """
        抽取单个事件
        
        Args:
            text: 输入文本
            domain: 领域
            event_type: 事件类型
            metadata: 元数据
            validate_result: 是否验证结果（None时使用服务默认设置）
            
        Returns:
            抽取结果字典
        """
        if not self.extractor:
            raise RuntimeError("服务未初始化，请先调用initialize()")
        
        start_time = datetime.now()
        self.stats["total_extractions"] += 1
        
        try:
            # 执行抽取
            result = await self.extractor.extract_single_event(
                text=text,
                domain=domain,
                event_type=event_type,
                metadata=metadata or {}
            )
            
            # 添加服务级别的元数据
            result["metadata"].update({
                "service_version": "1.0.0",
                "extraction_time": datetime.now().isoformat(),
                "processing_duration": (datetime.now() - start_time).total_seconds()
            })
            
            # 验证结果
            should_validate = validate_result if validate_result is not None else self.enable_validation
            if should_validate and self.validator:
                validation_result = self.validator.validate_extraction_result(result, domain, event_type)
                result["validation"] = {
                    "is_valid": validation_result.is_valid,
                    "quality_metrics": validation_result.quality_metrics,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "suggestions": validation_result.suggestions
                }
                
                if validation_result.is_valid:
                    self.stats["validation_passed"] += 1
                else:
                    self.stats["validation_failed"] += 1
            
            # 更新统计
            if result["metadata"].get("extraction_status") == "success":
                self.stats["successful_extractions"] += 1
            else:
                self.stats["failed_extractions"] += 1
            
            if self.enable_logging:
                logger.info(f"单事件抽取完成: {domain}.{event_type}, 状态: {result['metadata'].get('extraction_status')}")
            
            return result
            
        except Exception as e:
            self.stats["failed_extractions"] += 1
            logger.error(f"单事件抽取失败: {str(e)}")
            
            return {
                "event_data": None,
                "metadata": {
                    "extraction_status": "error",
                    "error_message": str(e),
                    "confidence_score": 0.0,
                    "domain": domain,
                    "event_type": event_type,
                    "service_version": "1.0.0",
                    "extraction_time": datetime.now().isoformat(),
                    "processing_duration": (datetime.now() - start_time).total_seconds()
                }
            }
    
    async def extract_multiple_events(self,
                                    text: str,
                                    target_domains: Optional[List[str]] = None,
                                    metadata: Optional[Dict[str, Any]] = None,
                                    validate_results: bool = None) -> List[Dict[str, Any]]:
        """
        抽取多个事件
        
        Args:
            text: 输入文本
            target_domains: 目标领域列表
            metadata: 元数据
            validate_results: 是否验证结果
            
        Returns:
            抽取结果列表
        """
        if not self.extractor:
            raise RuntimeError("服务未初始化，请先调用initialize()")
        
        start_time = datetime.now()
        
        try:
            # 执行多事件抽取
            results = await self.extractor.extract_multi_events(
                text=text,
                target_domains=target_domains,
                metadata=metadata or {}
            )
            
            # 批量验证
            should_validate = validate_results if validate_results is not None else self.enable_validation
            if should_validate and self.validator and results:
                for result in results:
                    domain = result["metadata"].get("domain")
                    event_type = result["metadata"].get("event_type")
                    
                    if domain and event_type:
                        validation_result = self.validator.validate_extraction_result(result, domain, event_type)
                        result["validation"] = {
                            "is_valid": validation_result.is_valid,
                            "quality_metrics": validation_result.quality_metrics,
                            "errors": validation_result.errors,
                            "warnings": validation_result.warnings,
                            "suggestions": validation_result.suggestions
                        }
            
            # 更新统计
            self.stats["total_extractions"] += len(results)
            for result in results:
                if result["metadata"].get("extraction_status") == "success":
                    self.stats["successful_extractions"] += 1
                else:
                    self.stats["failed_extractions"] += 1
            
            if self.enable_logging:
                logger.info(f"多事件抽取完成: 抽取到 {len(results)} 个事件")
            
            return results
            
        except Exception as e:
            logger.error(f"多事件抽取失败: {str(e)}")
            return []
    
    async def batch_extract(self,
                          texts: List[str],
                          domain: str,
                          event_type: str,
                          batch_size: Optional[int] = None,
                          metadata_list: Optional[List[Dict[str, Any]]] = None,
                          validate_results: bool = None) -> List[Dict[str, Any]]:
        """
        批量抽取事件
        
        Args:
            texts: 文本列表
            domain: 领域
            event_type: 事件类型
            batch_size: 批量大小
            metadata_list: 元数据列表
            validate_results: 是否验证结果
            
        Returns:
            抽取结果列表
        """
        if not self.extractor:
            raise RuntimeError("服务未初始化，请先调用initialize()")
        
        start_time = datetime.now()
        
        try:
            # 执行批量抽取
            results = await self.extractor.batch_extract(
                texts=texts,
                domain=domain,
                event_type=event_type,
                batch_size=batch_size or self.config.batch_size,
                metadata_list=metadata_list
            )
            
            # 批量验证
            should_validate = validate_results if validate_results is not None else self.enable_validation
            if should_validate and self.validator:
                validation_results = self.validator.batch_validate(results, domain, event_type)
                
                for result, validation_result in zip(results, validation_results):
                    result["validation"] = {
                        "is_valid": validation_result.is_valid,
                        "quality_metrics": validation_result.quality_metrics,
                        "errors": validation_result.errors,
                        "warnings": validation_result.warnings,
                        "suggestions": validation_result.suggestions
                    }
            
            # 更新统计
            self.stats["total_extractions"] += len(results)
            for result in results:
                if result["metadata"].get("extraction_status") == "success":
                    self.stats["successful_extractions"] += 1
                else:
                    self.stats["failed_extractions"] += 1
            
            if self.enable_logging:
                logger.info(f"批量抽取完成: 处理 {len(texts)} 个文本，成功 {len(results)} 个")
            
            return results
            
        except Exception as e:
            logger.error(f"批量抽取失败: {str(e)}")
            return []
    
    def get_supported_domains(self) -> List[str]:
        """
        获取支持的领域列表
        
        Returns:
            支持的领域列表
        """
        if self.extractor:
            return self.extractor.get_supported_domains()
        return []
    
    def get_supported_event_types(self, domain: str) -> List[str]:
        """
        获取指定领域支持的事件类型
        
        Args:
            domain: 领域名称
            
        Returns:
            事件类型列表
        """
        if self.extractor:
            return self.extractor.get_supported_event_types(domain)
        return []
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务统计信息
        
        Returns:
            统计信息字典
        """
        current_time = datetime.now()
        uptime = (current_time - self.stats["start_time"]).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "total_extractions": self.stats["total_extractions"],
            "successful_extractions": self.stats["successful_extractions"],
            "failed_extractions": self.stats["failed_extractions"],
            "success_rate": (
                self.stats["successful_extractions"] / self.stats["total_extractions"]
                if self.stats["total_extractions"] > 0 else 0
            ),
            "validation_passed": self.stats["validation_passed"],
            "validation_failed": self.stats["validation_failed"],
            "validation_rate": (
                self.stats["validation_passed"] / (self.stats["validation_passed"] + self.stats["validation_failed"])
                if (self.stats["validation_passed"] + self.stats["validation_failed"]) > 0 else 0
            ),
            "average_extractions_per_minute": (
                self.stats["total_extractions"] / (uptime / 60)
                if uptime > 0 else 0
            )
        }
    
    def reset_stats(self):
        """
        重置统计信息
        """
        self.stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "start_time": datetime.now()
        }
        logger.info("服务统计信息已重置")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态字典
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "extractor": self.extractor is not None,
                "validator": self.validator is not None,
                "template_generator": self.template_generator is not None
            },
            "config": {
                "model_name": self.config.model_name,
                "validation_enabled": self.enable_validation,
                "logging_enabled": self.enable_logging
            }
        }
        
        # 检查API连接
        try:
            if self.extractor:
                # 执行一个简单的测试抽取
                test_result = await self.extractor.extract_single_event(
                    text="测试文本",
                    domain="financial",
                    event_type="company_merger_and_acquisition",
                    metadata={"health_check": True}
                )
                health_status["api_connection"] = True
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["api_connection"] = False
            health_status["error"] = str(e)
        
        return health_status
    
    async def shutdown(self):
        """
        关闭服务
        """
        logger.info("正在关闭事件抽取服务...")
        
        # 记录最终统计
        final_stats = self.get_service_stats()
        logger.info(f"服务运行统计: {final_stats}")
        
        # 清理资源
        self.extractor = None
        self.validator = None
        self.template_generator = None
        
        logger.info("事件抽取服务已关闭")

# 便捷函数
async def create_extraction_service(config_name: str = "default", **kwargs) -> EventExtractionService:
    """
    创建并初始化事件抽取服务
    
    Args:
        config_name: 配置名称
        **kwargs: 其他参数
        
    Returns:
        初始化完成的EventExtractionService实例
    """
    service = EventExtractionService(config_name=config_name, **kwargs)
    await service.initialize()
    return service

async def quick_extract(text: str, 
                       domain: str, 
                       event_type: str,
                       config_name: str = "fast") -> Dict[str, Any]:
    """
    快速事件抽取（一次性使用）
    
    Args:
        text: 输入文本
        domain: 领域
        event_type: 事件类型
        config_name: 配置名称
        
    Returns:
        抽取结果
    """
    service = await create_extraction_service(config_name=config_name)
    try:
        result = await service.extract_single_event(text, domain, event_type)
        return result
    finally:
        await service.shutdown()

if __name__ == "__main__":
    # 示例用法
    async def main():
        # 创建服务
        service = await create_extraction_service("default")
        
        try:
            # 健康检查
            health = await service.health_check()
            print(f"服务健康状态: {health['status']}")
            
            # 测试单事件抽取
            test_text = """
            2024年1月15日，腾讯控股有限公司宣布以120亿美元的价格收购字节跳动旗下的TikTok业务。
            此次并购交易预计将在2024年第二季度完成。
            """
            
            result = await service.extract_single_event(
                text=test_text,
                domain="financial",
                event_type="company_merger_and_acquisition"
            )
            
            print(f"抽取结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            # 获取统计信息
            stats = service.get_service_stats()
            print(f"服务统计: {stats}")
            
        finally:
            await service.shutdown()
    
    # 运行示例
    asyncio.run(main())