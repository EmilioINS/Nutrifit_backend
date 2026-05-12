-- Schema para el Sistema de Rachas en NutriFit
-- Ejecuta este script en el SQL Editor de Supabase

-- 1. Tabla para rastrear la racha general del usuario
CREATE TABLE IF NOT EXISTS public.streaks (
    user_id UUID PRIMARY KEY REFERENCES public.users_profile(id) ON DELETE CASCADE,
    current_streak INT DEFAULT 0,
    highest_streak INT DEFAULT 0,
    last_completed_date DATE,
    restore_chances INT DEFAULT 3,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 2. Tabla para rastrear el completado diario de comidas
CREATE TABLE IF NOT EXISTS public.daily_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users_profile(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    completed_meals JSONB DEFAULT '[]'::jsonb, -- Array de nombres de comidas completadas, ej: ["Desayuno", "Cena"]
    total_expected_meals INT NOT NULL,
    is_day_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE (user_id, date) -- Un solo registro por usuario por día
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_daily_logs_user_date ON public.daily_logs(user_id, date);
