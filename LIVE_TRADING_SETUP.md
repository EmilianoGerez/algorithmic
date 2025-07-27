# Live Trading Setup Guide

This guide shows you how to set up API keys for live trading with the quantitative trading platform.

## API Key Setup

### Option 1: Environment Variables (Recommended)

Create a `.env` file in your project root directory:

```bash
# Create .env file in the project root
cd /Users/emilianogerez/Projects/python/algorithmic
touch .env
```

Add your API keys to the `.env` file:

```bash
# Binance Testnet API Keys
BINANCE_API_KEY=your_binance_testnet_api_key_here
BINANCE_API_SECRET=your_binance_testnet_secret_here

# Alpaca Paper Trading API Keys
ALPACA_API_KEY=your_alpaca_paper_api_key_here
ALPACA_API_SECRET=your_alpaca_paper_secret_here
```

### Option 2: System Environment Variables

You can also set environment variables directly in your shell:

```bash
# For current session only
export BINANCE_API_KEY="your_binance_testnet_api_key_here"
export BINANCE_API_SECRET="your_binance_testnet_secret_here"
export ALPACA_API_KEY="your_alpaca_paper_api_key_here"
export ALPACA_API_SECRET="your_alpaca_paper_secret_here"

# Or add to your shell profile (~/.zshrc, ~/.bashrc)
echo 'export BINANCE_API_KEY="your_key"' >> ~/.zshrc
echo 'export BINANCE_API_SECRET="your_secret"' >> ~/.zshrc
```

## Getting API Keys

### Binance Testnet (Cryptocurrency Futures)

1. Go to [Binance Testnet](https://testnet.binancefuture.com/)
2. Create an account (separate from main Binance)
3. Generate API keys:
   - Go to API Management
   - Create new API key
   - Enable "Futures" permissions
   - Save both API Key and Secret Key
4. **Important**: These are testnet keys with fake money - safe for testing!

### Alpaca Paper Trading (US Stocks)

1. Go to [Alpaca Markets](https://alpaca.markets/)
2. Sign up for a free account
3. Go to "Paper Trading" section
4. Generate API keys:
   - Dashboard → API Keys → Generate New Key
   - Choose "Paper Trading" environment
   - Save both Key ID and Secret Key
5. **Important**: Paper trading uses virtual money - safe for testing!

## Security Best Practices

1. **Never commit API keys to git**:

   ```bash
   # Add .env to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use testnet/paper trading only** - The system is configured for safety:

   - Binance: Always uses testnet (fake money)
   - Alpaca: Always uses paper trading (virtual money)

3. **Rotate keys regularly** - Generate new keys periodically

## Testing Your Setup

### Test Binance Connection

```bash
# Set your keys first
export BINANCE_API_KEY="your_testnet_key"
export BINANCE_API_SECRET="your_testnet_secret"

# Test connection
python -m services.cli.cli run --config configs/base.yaml --live binance --verbose
```

### Test Alpaca Connection

```bash
# Set your keys first
export ALPACA_API_KEY="your_paper_key"
export ALPACA_API_SECRET="your_paper_secret"

# Test connection
python -m services.cli.cli run --config configs/base.yaml --live alpaca --verbose
```

## Usage Examples

### Live Trading Commands

```bash
# Binance Futures (Crypto) - uses testnet
python -m services.cli.cli run --config configs/base.yaml --live binance --verbose

# Alpaca Stocks - uses paper trading
python -m services.cli.cli run --config configs/base.yaml --live alpaca --verbose

# Help and options
python -m services.cli.cli run --help
```

### Configuration Options

The system automatically configures itself for live trading:

- **Execution mode**: Switches from backtest to live
- **Broker selection**: Routes orders to specified broker
- **Position reconciliation**: Monitors for drift every 30 seconds
- **Safety**: Always uses test environments (testnet/paper)

## Troubleshooting

### Common Issues

1. **"Missing API credentials"**:

   - Check your .env file exists and has correct variable names
   - Verify environment variables are set: `echo $BINANCE_API_KEY`

2. **"Invalid credentials"**:

   - Double-check API key and secret are correct
   - Ensure using testnet keys for Binance
   - Ensure using paper trading keys for Alpaca

3. **"Connection failed"**:
   - Check internet connection
   - Verify API keys have proper permissions
   - Check broker API status pages

### Getting Help

- Check logs with `--verbose` flag for detailed error messages
- Verify API key permissions on broker websites
- Test with curl/postman first to isolate issues

## File Locations

```
/Users/emilianogerez/Projects/python/algorithmic/
├── .env                          # ← Place your API keys here
├── configs/base.yaml            # Configuration file
├── services/cli/cli.py          # CLI interface
├── infra/brokers/               # Broker implementations
│   ├── binance_futures.py       # Binance testnet
│   └── alpaca.py                # Alpaca paper trading
└── tests/integration/           # Integration tests
```

## Next Steps

1. Set up your API keys following this guide
2. Test connections with both brokers
3. Start with small positions for live testing
4. Monitor reconciliation logs for any position drift
5. Ready for live algorithmic trading! 🚀
