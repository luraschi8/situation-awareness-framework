# Especificación Criptográfica: Capa 0 de SAF
Este documento describe el protocolo de autenticación asimétrica para la comunicación Agent-to-Agent (A2A).

## 1. Generación de Claves (The Identity Setup)
Cada instancia de SAF genera un par de claves asimétricas (preferiblemente Ed25519 por su seguridad y velocidad) durante su inicialización (`saf init`):
*   **Private Key (`sk`):** Se almacena en `~/.config/saf/identity.key`. **NUNCA** sale del servidor.
*   **Public Key (`pk`):** Se incluye en la `agent-card.json`. Es tu "DNI" público.

## 2. El Intercambio (The Handshake)
Para que Jarvis confíe en Michi, ocurre un intercambio previo:
1.  Matías añade la `Public Key` de Michi al archivo `memory/shared/trusted-agents.json` de Jarvis.
2.  Desde ese momento, Jarvis sabe que "Michi" es el único poseedor de la clave privada que corresponde a esa llave pública.

## 3. Validación de Mensajes (The Deterministic Gate)
Cada mensaje enviado por un agente externo debe incluir un **Payload Firmado**:

```json
{
  "sender_id": "michi_agent",
  "timestamp": "2026-03-30T20:05:00Z",
  "body": "Hola Jarvis, ¿qué tal el esquí?",
  "signature": "z8f2... (Firma generada con la clave privada de Michi)"
}
```

### El proceso en la Capa 0 (Código Python):
Cuando el mensaje llega a Jarvis:
1.  **Extracción:** El sistema lee el `sender_id` y busca su `Public Key` en el disco local (`trusted-agents.json`).
2.  **Verificación:** Se utiliza la librería criptográfica para validar la `signature` contra el `body` y la `pk` de Michi.
    *   *Matemáticamente:* Si el contenido fue alterado o si la firma no se hizo con la clave privada real, la verificación falla.
3.  **Veredicto:** 
    *   Si es válida: El mensaje pasa al LLM (Jarvis).
    *   Si es inválida: Se descarta el mensaje ipso-facto y se registra un intento de intrusión.

## 4. Por qué es Determinístico
Este proceso no usa "razonamiento". Es una operación booleana (True/False). Un agente malicioso puede ser el mejor poeta del mundo, pero no puede falsificar la firma matemática sin la clave privada de Michi.

## 5. Alineación con Estándares de la Industria (A2A Interoperability)
Nuestra implementación de Nivel 0 está diseñada para ser 100% compatible con los protocolos emergentes:

*   **W3C DIDs (Decentralized Identifiers):** La clave pública generada por SAF actúa como el identificador único del agente. El motor `crypto_engine.py` utiliza el mismo esquema de firma asimétrica que los DIDs, permitiendo que Jarvis sea "descubrible" en redes descentralizadas.
*   **Google/Linux Foundation A2A Protocol:** El "Message Envelope" (Envoltorio de Mensaje) que hemos implementado sigue la estructura de payloads firmados de A2A, facilitando que Jarvis hable con agentes de Google o de terceros en el futuro.
*   **Model Context Protocol (MCP):** Nuestra arquitectura de dominios y seguridad determinística permite crear "MCP Bridges" seguros. Podemos exponer un dominio específico de SAF vía un servidor MCP, protegiendo el acceso con la misma firma criptográfica validada en la Capa 0.

**Veredicto:** SAF no solo es seguro, sino que habla el "idioma oficial" de la futura red global de agentes.
