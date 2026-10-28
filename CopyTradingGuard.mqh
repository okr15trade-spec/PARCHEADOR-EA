//+------------------------------------------------------------------+
//|                                          CopyTradingGuard.mqh    |
//|  Guardián para EAs de estrategia: lee la señal que publica el    |
//|  EA CopyTrading_Master (archivo en la carpeta Common\Files) y    |
//|  permite saber si se pueden abrir operaciones nuevas.            |
//|                                                                  |
//|  Uso manual (si no usas el parcheador):                          |
//|    1) #include "CopyTradingGuard.mqh"  (junto a tus includes)    |
//|    2) Antes de enviar cualquier orden de ENTRADA:                |
//|         if(!CTG_AllowOpen()) return;                             |
//|                                                                  |
//|  Estados de la señal:  0 = libre | 1 = sin entradas nuevas       |
//|                        2 = bloqueo total (Master cerró todo)     |
//+------------------------------------------------------------------+
#ifndef COPYTRADING_GUARD_MQH
#define COPYTRADING_GUARD_MQH

input string CTG_GuardFile  = "CopyTrading\\guard.txt"; // CTG: archivo de señal del Master (carpeta Common\Files)
input int    CTG_StaleSec   = 120;                       // CTG: segundos sin latido del Master para dar la señal por caducada (0 = nunca)
input bool   CTG_FailClosed = false;                     // CTG: true = si falta la señal o caduca, NO abrir operaciones

int      g_ctg_state    = 0;
string   g_ctg_reason   = "";
datetime g_ctg_lastRead = 0;
bool     g_ctg_loaded   = false;
int      g_ctg_lastLogged = -1;

//+------------------------------------------------------------------+
//| Lee la señal (máximo una vez por segundo)                        |
//+------------------------------------------------------------------+
void CTG_Refresh()
{
   // En el probador de estrategias no hay Master: no se aplica ningún bloqueo
   if(MQLInfoInteger(MQL_TESTER) != 0 || MQLInfoInteger(MQL_OPTIMIZATION) != 0)
   {
      g_ctg_state = 0;
      g_ctg_loaded = true;
      return;
   }

   datetime now = TimeLocal();
   if(g_ctg_loaded && now == g_ctg_lastRead)
      return;
   g_ctg_lastRead = now;

   int state = 0;
   string reason = "";
   long hb = 0;

   int h = FileOpen(CTG_GuardFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      if(CTG_FailClosed)
      {
         state = 2;
         reason = "no se encuentra la senal del Master";
      }
   }
   else
   {
      while(!FileIsEnding(h))
      {
         string line = FileReadString(h);
         int p = StringFind(line, "=");
         if(p < 0)
            continue;
         string k = StringSubstr(line, 0, p);
         string v = StringSubstr(line, p + 1);
         StringTrimRight(v);
         if(k == "state")
            state = (int)StringToInteger(v);
         else if(k == "reason")
            reason = v;
         else if(k == "heartbeat")
            hb = StringToInteger(v);
      }
      FileClose(h);

      if(CTG_StaleSec > 0 && hb > 0 && ((long)TimeGMT() - hb) > CTG_StaleSec)
      {
         state = CTG_FailClosed ? 2 : 0;
         reason = CTG_FailClosed ? "senal caducada (el Master no responde)" : "";
      }
   }

   g_ctg_state = state;
   g_ctg_reason = reason;
   g_ctg_loaded = true;

   if(g_ctg_state != g_ctg_lastLogged)
   {
      g_ctg_lastLogged = g_ctg_state;
      if(g_ctg_state == 0)
         Print("CopyTradingGuard: trading habilitado");
      else
         Print("CopyTradingGuard: entradas bloqueadas (estado ", g_ctg_state, ") ", g_ctg_reason);
   }
}

//+------------------------------------------------------------------+
//| true = se pueden abrir operaciones nuevas                        |
//+------------------------------------------------------------------+
bool CTG_AllowOpen()
{
   CTG_Refresh();
   return(g_ctg_state == 0);
}

//+------------------------------------------------------------------+
//| true = bloqueo total (el Master ha cerrado todo)                 |
//+------------------------------------------------------------------+
bool CTG_Blocked()
{
   CTG_Refresh();
   return(g_ctg_state >= 2);
}

//+------------------------------------------------------------------+
//| Motivo del bloqueo (texto)                                       |
//+------------------------------------------------------------------+
string CTG_Reason()
{
   return(g_ctg_reason);
}

//+------------------------------------------------------------------+
//| Alternativa si no puedes tocar el punto de entrada de órdenes:   |
//| ponla al principio de OnTick():  if(CTG_SkipTick()) return;      |
//| Con bloqueo total salta el tick; con bloqueo parcial solo lo     |
//| salta si no hay posiciones ni órdenes abiertas en la cuenta.     |
//+------------------------------------------------------------------+
bool CTG_SkipTick()
{
   CTG_Refresh();
   if(g_ctg_state >= 2)
      return(true);
   if(g_ctg_state == 1 && PositionsTotal() == 0 && OrdersTotal() == 0)
      return(true);
   return(false);
}

#endif
