from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple


class BaseNotifier(ABC):
    """Abstract base class for all notifiers."""

    @abstractmethod
    def notify_change(
        self,
        endpoint: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        """Notify about a change in an endpoint.

        Args:
            endpoint: The URL of the endpoint that changed
            fields: List of tuples containing (field_name, field_value) for each field to display

        Returns:
            bool: True if notification was successful, False otherwise
        """
        pass

    @abstractmethod
    def notify_error(
        self,
        endpoint: str,
        error_message: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        """Notify about an error accessing an endpoint.

        Args:
            endpoint: The URL of the endpoint that had an error
            error_message: Description of the error
            fields: List of tuples containing (field_name, field_value) for each field to display

        Returns:
            bool: True if notification was successful, False otherwise
        """
        pass

    @abstractmethod
    def notify_warning(
        self,
        endpoint: str,
        warning_message: str,
        fields: List[Tuple[str, str]],
    ) -> bool:
        """Notify about a warning for an endpoint.

        Args:
            endpoint: The URL of the endpoint that has a warning
            warning_message: Description of the warning
            fields: List of tuples containing (field_name, field_value) for each field to display

        Returns:
            bool: True if notification was successful, False otherwise
        """
        pass
