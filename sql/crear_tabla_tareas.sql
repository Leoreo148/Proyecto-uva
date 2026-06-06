-- =============================================
-- TABLA: Tareas_Evaluador
-- Ejecutar en Supabase > SQL Editor > New Query
-- =============================================

CREATE TABLE IF NOT EXISTS "Tareas_Evaluador" (
    id BIGSERIAL PRIMARY KEY,
    "Fecha" DATE NOT NULL DEFAULT CURRENT_DATE,
    "Modulo" TEXT NOT NULL,
    "Sector" TEXT NOT NULL,
    "Prioridad" TEXT DEFAULT '🟢 Normal',
    "Instrucciones" TEXT,
    "Estado" TEXT DEFAULT 'Pendiente',
    "Asignado_por" TEXT,
    "Rol_Asignador" TEXT,
    "Completada_a" TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar acceso desde la API (RLS)
ALTER TABLE "Tareas_Evaluador" ENABLE ROW LEVEL SECURITY;

-- Política: permitir todo desde la API (tu app ya tiene candados por rol)
CREATE POLICY "Acceso completo Tareas_Evaluador" ON "Tareas_Evaluador"
    FOR ALL USING (true) WITH CHECK (true);

-- Índice para consultas rápidas por fecha
CREATE INDEX idx_tareas_fecha ON "Tareas_Evaluador" ("Fecha");
