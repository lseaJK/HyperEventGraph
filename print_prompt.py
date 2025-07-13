from src.event_extraction.prompt_templates import PromptTemplateGenerator

def main():
    """
    生成并打印多事件抽取的提示词。
    """
    try:
        generator = PromptTemplateGenerator()
        prompt = generator.generate_multi_event_prompt()
        print("--- 多事件抽取提示词 ---")
        print(prompt)
        print("------------------------")
    except Exception as e:
        print(f"生成提示词时出错: {e}")

if __name__ == "__main__":
    main()
