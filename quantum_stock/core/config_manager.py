# -*- coding: utf-8 -*-
"""
Configuration Manager for VN-QUANT
===================================
Centralized configuration management with validation and type safety.

Features:
- Environment variable loading
- Type validation
- Default values
- Configuration validation
- Hot reload support
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from dotenv import load_dotenv


class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"


class DataProvider(Enum):
    VCI = "vci"
    SSI = "ssi"
    FIREANT = "fireant"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "postgresql://vnquant:password@localhost:5432/vnquant_db"
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False

    @classmethod
    def from_env(cls):
        return cls(
            url=os.getenv("DATABASE_URL", cls.url),
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", cls.pool_size)),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", cls.max_overflow))
        )


@dataclass
class RedisConfig:
    """Redis configuration"""
    url: str = "redis://localhost:6379/0"
    password: Optional[str] = None
    decode_responses: bool = True

    @classmethod
    def from_env(cls):
        return cls(
            url=os.getenv("REDIS_URL", cls.url),
            password=os.getenv("REDIS_PASSWORD", cls.password)
        )


@dataclass
class TradingConfig:
    """Trading configuration"""
    mode: TradingMode = TradingMode.PAPER
    initial_capital: float = 100_000_000  # 100M VND
    max_position_pct: float = 0.15
    max_positions: int = 10
    stop_loss_pct: float = 0.07
    take_profit_pct: float = 0.15
    max_daily_loss_pct: float = 0.05
    auto_trade_enabled: bool = False
    auto_scan_interval: int = 300  # seconds
    trading_fee_pct: float = 0.0015
    advance_fee_pct: float = 0.0003
    settlement_days: int = 3

    @classmethod
    def from_env(cls):
        mode_str = os.getenv("TRADING_MODE", "paper")
        return cls(
            mode=TradingMode(mode_str),
            initial_capital=float(os.getenv("INITIAL_CAPITAL", cls.initial_capital)),
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", cls.max_position_pct)),
            max_positions=int(os.getenv("MAX_POSITIONS", cls.max_positions)),
            stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", cls.stop_loss_pct)),
            take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", cls.take_profit_pct)),
            max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", cls.max_daily_loss_pct)),
            auto_trade_enabled=os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true",
            auto_scan_interval=int(os.getenv("AUTO_SCAN_INTERVAL", cls.auto_scan_interval))
        )


@dataclass
class APIConfig:
    """API server configuration"""
    host: str = "0.0.0.0"
    port: int = 8003
    workers: int = 4
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:5176"])
    rate_limit_per_minute: int = 60

    @classmethod
    def from_env(cls):
        origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5176")
        return cls(
            host=os.getenv("API_HOST", cls.host),
            port=int(os.getenv("API_PORT", cls.port)),
            workers=int(os.getenv("API_WORKERS", cls.workers)),
            cors_origins=origins_str.split(","),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", cls.rate_limit_per_minute))
        )


@dataclass
class SecurityConfig:
    """Security configuration"""
    jwt_secret: str = "change_this_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600  # seconds
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls):
        return cls(
            jwt_secret=os.getenv("JWT_SECRET", cls.jwt_secret),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", cls.jwt_algorithm),
            jwt_expiration=int(os.getenv("JWT_EXPIRATION", cls.jwt_expiration)),
            api_key=os.getenv("API_KEY")
        )


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    grafana_url: Optional[str] = None
    grafana_api_key: Optional[str] = None
    alert_email: Optional[str] = None
    alert_webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    @classmethod
    def from_env(cls):
        return cls(
            prometheus_enabled=os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", cls.prometheus_port)),
            grafana_url=os.getenv("GRAFANA_URL"),
            grafana_api_key=os.getenv("GRAFANA_API_KEY"),
            alert_email=os.getenv("ALERT_EMAIL"),
            alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
        )


@dataclass
class BrokerConfig:
    """Broker credentials configuration"""
    # SSI
    ssi_username: Optional[str] = None
    ssi_password: Optional[str] = None
    ssi_api_key: Optional[str] = None
    ssi_secret_key: Optional[str] = None

    # VNDIRECT
    vndirect_username: Optional[str] = None
    vndirect_password: Optional[str] = None
    vndirect_api_key: Optional[str] = None

    # VPS
    vps_username: Optional[str] = None
    vps_password: Optional[str] = None

    @classmethod
    def from_env(cls):
        return cls(
            ssi_username=os.getenv("SSI_USERNAME"),
            ssi_password=os.getenv("SSI_PASSWORD"),
            ssi_api_key=os.getenv("SSI_API_KEY"),
            ssi_secret_key=os.getenv("SSI_SECRET_KEY"),
            vndirect_username=os.getenv("VNDIRECT_USERNAME"),
            vndirect_password=os.getenv("VNDIRECT_PASSWORD"),
            vndirect_api_key=os.getenv("VNDIRECT_API_KEY"),
            vps_username=os.getenv("VPS_USERNAME"),
            vps_password=os.getenv("VPS_PASSWORD")
        )


@dataclass
class Config:
    """
    Main configuration class

    Aggregates all configuration sections
    """
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: str = "INFO"

    # API Keys
    gemini_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_admin_ids: List[int] = field(default_factory=list)
    finnhub_api_key: Optional[str] = None

    # Sub-configs
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    api: APIConfig = field(default_factory=APIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)

    # Data settings
    data_provider: DataProvider = DataProvider.VCI
    cache_ttl: int = 300
    data_dir: str = "data"
    historical_data_dir: str = "data/historical"

    # Timezone
    timezone: str = "Asia/Ho_Chi_Minh"

    @classmethod
    def from_env(cls, env_file: Optional[str] = None):
        """
        Load configuration from environment variables

        Args:
            env_file: Path to .env file (default: .env in project root)

        Returns:
            Config instance
        """
        # Load .env file
        if env_file is None:
            env_file = Path(__file__).parent.parent.parent / ".env"

        if Path(env_file).exists():
            load_dotenv(env_file)

        # Parse environment
        env_str = os.getenv("ENVIRONMENT", "development")
        environment = Environment(env_str)

        # Parse admin IDs
        admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

        # Parse data provider
        provider_str = os.getenv("DATA_PROVIDER", "vci")
        data_provider = DataProvider(provider_str)

        return cls(
            environment=environment,
            debug=os.getenv("DEBUG", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_admin_ids=admin_ids,
            finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            trading=TradingConfig.from_env(),
            api=APIConfig.from_env(),
            security=SecurityConfig.from_env(),
            monitoring=MonitoringConfig.from_env(),
            broker=BrokerConfig.from_env(),
            data_provider=data_provider,
            cache_ttl=int(os.getenv("CACHE_TTL", "300")),
            data_dir=os.getenv("DATA_DIR", "data"),
            historical_data_dir=os.getenv("HISTORICAL_DATA_DIR", "data/historical"),
            timezone=os.getenv("TZ", "Asia/Ho_Chi_Minh")
        )

    def validate(self) -> List[str]:
        """
        Validate configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields in production
        if self.environment == Environment.PRODUCTION:
            if not self.gemini_api_key:
                errors.append("GEMINI_API_KEY is required in production")

            if self.security.jwt_secret == "change_this_in_production":
                errors.append("JWT_SECRET must be changed in production")

            if self.trading.mode == TradingMode.LIVE:
                if not self.broker.ssi_username and not self.broker.vndirect_username:
                    errors.append("Broker credentials required for live trading")

            if self.debug:
                errors.append("DEBUG should be false in production")

        # Validate trading config
        if self.trading.max_position_pct <= 0 or self.trading.max_position_pct > 1:
            errors.append("MAX_POSITION_PCT must be between 0 and 1")

        if self.trading.max_positions <= 0:
            errors.append("MAX_POSITIONS must be positive")

        if self.trading.stop_loss_pct < 0 or self.trading.stop_loss_pct > 1:
            errors.append("STOP_LOSS_PCT must be between 0 and 1")

        # Validate API config
        if self.api.port < 1024 or self.api.port > 65535:
            errors.append("API_PORT must be between 1024 and 65535")

        if self.api.workers < 1:
            errors.append("API_WORKERS must be at least 1")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary (for serialization)"""
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "log_level": self.log_level,
            "trading_mode": self.trading.mode.value,
            "data_provider": self.data_provider.value,
            "auto_trade_enabled": self.trading.auto_trade_enabled,
            "api_port": self.api.port,
            "prometheus_enabled": self.monitoring.prometheus_enabled
        }

    def __repr__(self) -> str:
        """Safe string representation (no secrets)"""
        return (
            f"Config(environment={self.environment.value}, "
            f"trading_mode={self.trading.mode.value}, "
            f"auto_trade={self.trading.auto_trade_enabled})"
        )


# Global config instance
_config: Optional[Config] = None


def load_config(env_file: Optional[str] = None, validate: bool = True) -> Config:
    """
    Load global configuration

    Args:
        env_file: Path to .env file
        validate: Whether to validate config

    Returns:
        Config instance

    Raises:
        ValueError: If validation fails
    """
    global _config
    _config = Config.from_env(env_file)

    if validate:
        errors = _config.validate()
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

    return _config


def get_config() -> Config:
    """
    Get global configuration instance

    Returns:
        Config instance

    Raises:
        RuntimeError: If config not loaded
    """
    if _config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return _config


# Convenience exports
__all__ = [
    "Config",
    "Environment",
    "TradingMode",
    "DataProvider",
    "load_config",
    "get_config",
    "DatabaseConfig",
    "RedisConfig",
    "TradingConfig",
    "APIConfig",
    "SecurityConfig",
    "MonitoringConfig",
    "BrokerConfig"
]
