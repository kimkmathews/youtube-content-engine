from abc import ABC, abstractmethod

class BaseSkill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    def format_prompt(self, **kwargs) -> str:
        return self.get_system_prompt().format(**kwargs)
