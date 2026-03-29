# SAF v3.0: The Coordinator Era (Architecture Spec)

## 1. Global Collective Ledger (Refined Idea 1)
En lugar de archivos aislados, los agentes SAF operan sobre un **espacio de nombres compartido**.
- **Mecanismo:** `memory/shared/collective-ledger.json`.
- **Deduplicación Cross-Agent:** Si Michi registra `morning_briefing_sent` para María a las 08:05, Jarvis lo ve y puede referenciarlo: "María ya recibió su briefing, ¿quieres que te lo resuma?".

## 2. Dynamic Compute Pyramid (Refined Idea 2 + Intent)
El sistema ya no elige modelo por fase, sino por **Carga Cognitiva y Urgencia**.
- **L1 (Flash):** Consultas de estado, control de hogar, heartbeats.
- **L2 (Sonnet):** Gestión de agenda, redacción de informes, lógica de dominios.
- **L3 (Opus):** Planificación estratégica, debugging de arquitectura, resolución de conflictos entre agentes.

## 3. Intelligent Context Pruning (Refined Idea 3)
Eliminamos la búsqueda vectorial pesada en el 90% de los casos.
- **Protocolo:** La intención del usuario actúa como una llave de paso física. "Taxfix" bloquea Familia y Proyectos, inyectando solo el Dominio Trabajo.

## 4. Memetic Compression (Refined Idea 5)
La memoria no se borra, se **condensa por capas**.
- **Tier 1 (Eternal):** Hechos inamovibles (Cumpleaños, IDs de dispositivos).
- **Tier 2 (Active):** Contexto del mes (Proyecto LastingNote).
- **Tier 3 (Archive):** Logs de más de 30 días, accesibles solo vía `memory_search` bajo demanda.

## 5. Jarvis como Lead Agent (The Luraschi Cluster)
Jarvis deja de ser un "hacedor" para ser un **"Orquestador de Contexto"**.
- **Lead Agent Protocol (LAP):** Jarvis mantiene el SAF (Single Source of Truth). Cuando se requiere una tarea pesada (ej. crear el repo de GitHub), Jarvis no la hace; **despliega un sub-agente**, le entrega el "Fragmento de Dominio" necesario y audita el resultado.
- **Beneficio:** Escalabilidad infinita. Un solo cerebro (Jarvis) gestiona el estado de una familia entera delegando en operarios especializados.
