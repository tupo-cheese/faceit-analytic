"""Базовый анализатор."""
from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    name = "base"

    @abstractmethod
    def analyze(self, data, **kwargs):
        ...
