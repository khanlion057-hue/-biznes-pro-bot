-- Dillerlar bot uchun zakazlar jadvali
CREATE TABLE IF NOT EXISTS bot_orders (
  id BIGSERIAL PRIMARY KEY,
  dealer_id TEXT,
  dealer_name TEXT,
  dealer_chat_id BIGINT,
  items JSONB,
  total_usd DECIMAL(15,2),
  status TEXT DEFAULT 'new',
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE bot_orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_orders" ON bot_orders FOR ALL USING (true) WITH CHECK (true);

-- Dillerlar ro'yxati (bot orqali ro'yxatdan o'tganlar)
CREATE TABLE IF NOT EXISTS bot_dealers (
  chat_id BIGINT PRIMARY KEY,
  name TEXT,
  phone TEXT,
  approved BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE bot_dealers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_dealers" ON bot_dealers FOR ALL USING (true) WITH CHECK (true);
