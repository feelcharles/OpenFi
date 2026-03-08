//+------------------------------------------------------------------+
//|                                              Example EA          |
//|                                  OpenFi Example Expert Advisor   |
//+------------------------------------------------------------------+
#property copyright "OpenFi"
#property link      "https://github.com/openfi"
#property version   "1.00"
#property strict

// Input parameters
input double LotSize = 0.1;           // Lot size
input int    StopLoss = 50;           // Stop loss in points
input int    TakeProfit = 100;        // Take profit in points
input int    MA_Period = 14;          // Moving average period
input int    RSI_Period = 14;         // RSI period
input double RSI_Oversold = 30;       // RSI oversold level
input double RSI_Overbought = 70;     // RSI overbought level

// Global variables
int ma_handle;
int rsi_handle;
double ma_buffer[];
double rsi_buffer[];

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize indicators
   ma_handle = iMA(_Symbol, PERIOD_CURRENT, MA_Period, 0, MODE_SMA, PRICE_CLOSE);
   rsi_handle = iRSI(_Symbol, PERIOD_CURRENT, RSI_Period, PRICE_CLOSE);
   
   if(ma_handle == INVALID_HANDLE || rsi_handle == INVALID_HANDLE)
   {
      Print("Error creating indicators");
      return(INIT_FAILED);
   }
   
   ArraySetAsSeries(ma_buffer, true);
   ArraySetAsSeries(rsi_buffer, true);
   
   Print("Example EA initialized successfully");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(ma_handle);
   IndicatorRelease(rsi_handle);
   Print("Example EA deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Copy indicator values
   if(CopyBuffer(ma_handle, 0, 0, 3, ma_buffer) < 3) return;
   if(CopyBuffer(rsi_handle, 0, 0, 3, rsi_buffer) < 3) return;
   
   // Get current price
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // Check for open positions
   if(PositionsTotal() == 0)
   {
      // Buy signal: Price crosses above MA and RSI is oversold
      if(bid > ma_buffer[0] && rsi_buffer[0] < RSI_Oversold)
      {
         OpenPosition(ORDER_TYPE_BUY, ask);
      }
      // Sell signal: Price crosses below MA and RSI is overbought
      else if(bid < ma_buffer[0] && rsi_buffer[0] > RSI_Overbought)
      {
         OpenPosition(ORDER_TYPE_SELL, bid);
      }
   }
}

//+------------------------------------------------------------------+
//| Open position function                                           |
//+------------------------------------------------------------------+
void OpenPosition(ENUM_ORDER_TYPE type, double price)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = LotSize;
   request.type = type;
   request.price = price;
   request.deviation = 10;
   request.magic = 123456;
   
   // Calculate SL and TP
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(type == ORDER_TYPE_BUY)
   {
      request.sl = price - StopLoss * point;
      request.tp = price + TakeProfit * point;
   }
   else
   {
      request.sl = price + StopLoss * point;
      request.tp = price - TakeProfit * point;
   }
   
   if(!OrderSend(request, result))
   {
      Print("OrderSend error: ", GetLastError());
   }
   else
   {
      Print("Position opened successfully. Ticket: ", result.order);
   }
}
//+------------------------------------------------------------------+
