"""
Tests for risk management system components.

This module tests the risk configuration, position sizing calculations,
and trade validation logic to ensure proper risk management behavior.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from core.indicators.regime import Regime
from core.indicators.snapshot import IndicatorSnapshot
from core.risk.config import RiskConfig, RiskModel
from core.risk.manager import RiskManager
from core.strategy.signal_models import SignalDirection, TradingSignal, ZoneType
from core.trading.models import AccountState, Position


class TestRiskConfig:
    """Test risk configuration validation and settings."""

    def test_default_config(self) -> None:
        """Test default risk configuration values."""
        config = RiskConfig()

        assert config.model == RiskModel.ATR
        assert config.risk_per_trade == 0.01
        assert config.atr_period == 14
        assert config.sl_atr_multiple == 1.5
        assert config.tp_rr == 2.0
        assert config.min_position == 0.01
        assert config.max_position_pct == 0.1

    def test_config_validation(self) -> None:
        """Test configuration parameter validation."""
        # Invalid risk per trade
        with pytest.raises(
            ValueError, match="risk_per_trade must be between 0 and 0.1"
        ):
            RiskConfig(risk_per_trade=0.2)

        with pytest.raises(
            ValueError, match="risk_per_trade must be between 0 and 0.1"
        ):
            RiskConfig(risk_per_trade=0.0)

        # Invalid ATR period
        with pytest.raises(ValueError, match="atr_period must be positive"):
            RiskConfig(atr_period=0)

        # Invalid stop loss multiple
        with pytest.raises(ValueError, match="sl_atr_multiple must be positive"):
            RiskConfig(sl_atr_multiple=-1.0)

        # Invalid take profit ratio
        with pytest.raises(ValueError, match="tp_rr must be positive"):
            RiskConfig(tp_rr=0.0)

        # Invalid max position percentage
        with pytest.raises(
            ValueError, match="max_position_pct must be between 0 and 1"
        ):
            RiskConfig(max_position_pct=1.5)


class TestRiskManager:
    """Test risk manager position sizing and validation."""

    @pytest.fixture
    def risk_config(self) -> RiskConfig:
        """Standard risk configuration for testing."""
        return RiskConfig(
            model=RiskModel.ATR,
            risk_per_trade=0.01,  # 1% risk
            atr_period=14,
            sl_atr_multiple=1.5,
            tp_rr=2.0,
            max_position_pct=1.0,  # Allow up to 100% for testing
        )

    @pytest.fixture
    def risk_manager(self, risk_config: RiskConfig) -> RiskManager:
        """Risk manager instance for testing."""
        return RiskManager(risk_config)

    @pytest.fixture
    def account_state(self) -> AccountState:
        """Test account state with $100,000 equity to allow larger positions."""
        return AccountState(
            cash_balance=100000.0,
            equity=100000.0,
            positions={},
            realized_pnl=0.0,
        )

    @pytest.fixture
    def trading_signal(self) -> TradingSignal:
        """Test trading signal."""
        return TradingSignal(
            signal_id="test_signal_1",
            candidate_id="test_candidate_1",
            zone_id="test_zone",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            symbol="EURUSD",
            entry_price=1.2000,
            current_price=1.2000,
            strength=2.5,
            confidence=0.75,
            timestamp=datetime.utcnow(),
            timeframe="H1",
            metadata={},
        )

    @pytest.fixture
    def indicator_snapshot(self) -> IndicatorSnapshot:
        """Test indicator snapshot with ATR=0.001 (10 pips)."""
        return IndicatorSnapshot(
            timestamp=datetime.utcnow(),
            ema21=1.1990,
            ema50=1.1980,
            atr=0.001,  # 10 pips for EURUSD
            volume_sma=1000.0,
            regime=Regime.BULL,
            regime_with_slope=Regime.BULL,
            current_volume=1200.0,
            current_close=1.2000,
        )

    def test_atr_position_sizing_calculation(
        self,
        risk_manager: RiskManager,
        trading_signal: TradingSignal,
        account_state: AccountState,
        indicator_snapshot: IndicatorSnapshot,
    ) -> None:
        """Test ATR-based position sizing calculation.

        Expected calculation:
        - Account: $100,000
        - Risk per trade: 1% = $1,000
        - ATR: 0.001 (10 pips)
        - Stop distance: 1.5 * ATR = 0.0015 (15 pips)
        - Entry: 1.2000, Stop: 1.1985 (for long)
        - Risk per unit: 0.0015
        - Position size: $1,000 / 0.0015 = 666,666.67 units
        """
        sizing = risk_manager.size(trading_signal, account_state, indicator_snapshot)

        assert sizing is not None
        assert sizing.direction == SignalDirection.LONG
        assert sizing.entry_price == 1.2000
        assert sizing.risk_amount == 1000.0  # 1% of $100,000

        # Check stop loss calculation: entry - (1.5 * ATR)
        expected_stop = 1.2000 - (1.5 * 0.001)
        assert abs(sizing.stop_loss - expected_stop) < 1e-6

        # Check take profit calculation: entry + (1.5 * ATR * 2.0)
        expected_tp = 1.2000 + (1.5 * 0.001 * 2.0)
        assert abs(sizing.take_profit - expected_tp) < 1e-6

        # Check position size calculation - expect scaling due to max position limits
        risk_per_unit = abs(sizing.entry_price - sizing.stop_loss)
        raw_quantity = 1000.0 / risk_per_unit  # Raw calculation before scaling

        # Position value would be: raw_quantity * entry_price
        raw_position_value = raw_quantity * sizing.entry_price
        max_position_value = account_state.equity * 1.0  # 100% max position

        if raw_position_value > max_position_value:
            # Expect scaling to occur
            expected_scale_factor = max_position_value / raw_position_value
            expected_quantity = raw_quantity * expected_scale_factor
        else:
            expected_quantity = raw_quantity

        # Debug the calculation
        print(f"\nDEBUG: Entry={sizing.entry_price}, Stop={sizing.stop_loss}")
        print(f"DEBUG: Risk per unit={risk_per_unit}, Raw qty={raw_quantity}")
        print(
            f"DEBUG: Raw position value=${raw_position_value:,.0f}, Max=${max_position_value:,.0f}"
        )
        print(
            f"DEBUG: Expected qty={expected_quantity}, Actual qty={float(sizing.quantity)}"
        )

        # Check that the scaling was applied correctly
        assert (
            abs(float(sizing.quantity) - expected_quantity) < expected_quantity * 0.01
        )  # 1% tolerance

    def test_short_position_sizing(
        self,
        risk_manager: RiskManager,
        account_state: AccountState,
        indicator_snapshot: IndicatorSnapshot,
    ) -> None:
        """Test position sizing for short signals."""
        short_signal = TradingSignal(
            signal_id="test_short",
            candidate_id="test_candidate_short",
            zone_id="test_zone_short",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.SHORT,
            symbol="EURUSD",
            entry_price=1.2000,
            current_price=1.2000,
            strength=2.0,
            confidence=0.70,
            timestamp=datetime.utcnow(),
            timeframe="H1",
            metadata={},
        )

        sizing = risk_manager.size(short_signal, account_state, indicator_snapshot)

        assert sizing is not None
        assert sizing.direction == SignalDirection.SHORT
        assert float(sizing.quantity) < 0  # Negative quantity for short

        # Stop loss should be above entry for short
        assert sizing.stop_loss > sizing.entry_price

        # Take profit should be below entry for short
        assert sizing.take_profit < sizing.entry_price

    def test_insufficient_atr_data(
        self,
        risk_manager: RiskManager,
        trading_signal: TradingSignal,
        account_state: AccountState,
    ) -> None:
        """Test handling when ATR data is unavailable."""
        snapshot_no_atr = IndicatorSnapshot(
            timestamp=datetime.utcnow(),
            ema21=1.1990,
            ema50=1.1980,
            atr=None,  # No ATR data
            volume_sma=1000.0,
            regime=Regime.BULL,
            regime_with_slope=Regime.BULL,
            current_volume=1200.0,
            current_close=1.2000,
        )

        sizing = risk_manager.size(trading_signal, account_state, snapshot_no_atr)

        # Should return None when ATR is unavailable
        assert sizing is None

    def test_minimum_risk_amount(
        self,
        risk_manager: RiskManager,
        trading_signal: TradingSignal,
        indicator_snapshot: IndicatorSnapshot,
    ) -> None:
        """Test rejection of trades with too small risk amounts."""
        # Very small account
        small_account = AccountState(
            cash_balance=50.0,
            equity=50.0,
            positions={},
        )

        sizing = risk_manager.size(trading_signal, small_account, indicator_snapshot)

        # Should reject due to risk amount < $1
        assert sizing is None

    def test_position_size_limits(
        self,
        risk_manager: RiskManager,
        account_state: AccountState,
        indicator_snapshot: IndicatorSnapshot,
    ) -> None:
        """Test position size limiting based on max position percentage."""
        # Create signal that would result in large position
        high_price_signal = TradingSignal(
            signal_id="test_high_price",
            candidate_id="test_candidate_btc",
            zone_id="test_zone_btc",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            symbol="BTCUSD",
            entry_price=50000.0,  # High price
            current_price=50000.0,
            strength=2.0,
            confidence=0.65,
            timestamp=datetime.utcnow(),
            timeframe="H1",
            metadata={},
        )

        # Use snapshot with very small ATR to force large position
        small_atr_snapshot = IndicatorSnapshot(
            timestamp=datetime.utcnow(),
            ema21=49990.0,
            ema50=49980.0,
            atr=1.0,  # Very small ATR relative to price
            volume_sma=1000.0,
            regime=Regime.BULL,
            regime_with_slope=Regime.BULL,
            current_volume=1200.0,
            current_close=50000.0,
        )

        sizing = risk_manager.size(high_price_signal, account_state, small_atr_snapshot)

        assert sizing is not None

        # Check that position value is within limits
        position_value = abs(float(sizing.quantity)) * sizing.entry_price
        max_allowed = account_state.equity * risk_manager.config.max_position_pct
        assert position_value <= max_allowed * 1.01  # Allow small rounding error

    def test_signal_validation(
        self,
        risk_manager: RiskManager,
        trading_signal: TradingSignal,
        account_state: AccountState,
    ) -> None:
        """Test signal validation logic."""
        # Valid signal should pass
        assert risk_manager.validate_signal(trading_signal, account_state)

        # Low equity account should fail
        low_equity_account = AccountState(
            cash_balance=50.0,
            equity=50.0,
            positions={},
        )
        assert not risk_manager.validate_signal(trading_signal, low_equity_account)

        # Existing opposing position should fail
        existing_short_position = Position(
            symbol="EURUSD",
            quantity=Decimal("-1000"),  # Short position
            avg_entry_price=1.2010,
            current_price=1.2000,
            unrealized_pnl=10.0,
            entry_timestamp=datetime.utcnow(),
        )

        account_with_position = AccountState(
            cash_balance=10000.0,
            equity=10000.0,
            positions={"EURUSD": existing_short_position},
        )

        # Long signal should be rejected due to existing short position
        assert not risk_manager.validate_signal(trading_signal, account_with_position)

    def test_percent_risk_model(self) -> None:
        """Test percentage-based risk model."""
        percent_config = RiskConfig(model=RiskModel.PERCENT)
        risk_manager = RiskManager(percent_config)

        account_state = AccountState(
            cash_balance=10000.0,
            equity=10000.0,
            positions={},
        )

        trading_signal = TradingSignal(
            signal_id="test_percent",
            candidate_id="test_candidate_percent",
            zone_id="test_zone_percent",
            zone_type=ZoneType.POOL,
            direction=SignalDirection.LONG,
            symbol="EURUSD",
            entry_price=1.2000,
            current_price=1.2000,
            strength=2.0,
            confidence=0.80,
            timestamp=datetime.utcnow(),
            timeframe="H1",
            metadata={},
        )

        indicator_snapshot = IndicatorSnapshot(
            timestamp=datetime.utcnow(),
            ema21=1.1990,
            ema50=1.1980,
            atr=0.001,
            volume_sma=1000.0,
            regime=Regime.BULL,
            regime_with_slope=Regime.BULL,
            current_volume=1200.0,
            current_close=1.2000,
        )

        sizing = risk_manager.size(trading_signal, account_state, indicator_snapshot)

        assert sizing is not None
        assert sizing.direction == SignalDirection.LONG
        # Percent model uses different calculation, just ensure it works
        assert float(sizing.quantity) > 0
