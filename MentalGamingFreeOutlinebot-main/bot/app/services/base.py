"""
Base service class.

All concrete services should extend BaseService to inherit shared
infrastructure: logging, dependency injection of the DB session, and
common error handling.
"""

from __future__ import annotations

import logging
from typing import Optional

from database.connection import DatabaseManager


class BaseService:
    """
    Abstract base for all platform services.

    Attributes:
        db      Database manager providing async session access.
        logger  Logger scoped to the concrete subclass name.
    """

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        """
        Initialise the service.

        Args:
            db: Optional DatabaseManager instance.  When omitted the service
                uses the global singleton via DatabaseManager.get_instance().
        """
        self.db: DatabaseManager = db or DatabaseManager.get_instance()
        self.logger: logging.Logger = logging.getLogger(
            f"services.{self.__class__.__name__}"
        )
