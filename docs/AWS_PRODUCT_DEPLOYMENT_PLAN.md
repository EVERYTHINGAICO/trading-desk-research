# Plan de despliegue AWS para ofrecer el bot como producto

> Estado: plan guardado para implementación futura. No se despliega hoy.
> Fecha de referencia de precios: 2026-08-28, región us-east-1.
> Precios y supuestos deben validarse en `https://calculator.aws/` al momento de implementar.

## 1. Decisión: cuándo usar AWS

| Escenario | Solución | Costo estimado |
|---|---|---|
| Uso personal (1 usuario, tú) | Docker local actual | $0 (solo electricidad del servidor) |
| 1 suscriptor | Lightsail (~$5-7/mes) o EC2 t4g.micro (~$10/mes) | $5-10/mes |
| 5+ suscriptores | AWS Fargate + serverless (este plan) | $14-16/mes |
| Producto validado y creciendo | Fase 2 + 3 (RDS, ALB, más tareas) | crece según demanda |

Regla: **>5 usuarios pagando → AWS Fargate vale la pena.** Abajo de eso, local o instancia única.

La pieza central es **ECS Fargate**, no Lambda. EventBridge no soporta cron de 15 segundos y el bot es stateful (scheduler, locks, SQLite, procesos largos). Eso encaja en un contenedor continuo, no en invocaciones cortas.

## 2. Arquitectura objetivo

```text
                         PLANO COMERCIAL
┌─────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ Landing web │ Stripe │ API GW HTTP +    │ Lambda │ DynamoDB         │
│ S3+CF       │───────►│ Lambda webhook   │───────►│ usuarios/planes  │
└─────────────┘        │ (idempotente)    │        │ suscripciones    │
                       └──────────────────┘        └──────────────────┘

                         MOTOR DE TRADING
┌──────────────────┐  datos/APIs   ┌──────────────────────────┐
│ Binance + APIs   │──────────────►│ ECS Fargate (1 task)     │
│ pagadas          │               │ bot Docker continuo      │
└──────────────────┘               │ SQLite+EFS (Fase 1)      │
                                   └────────┬─────────────────┘
                                            │ alerta única
                                            ▼
                                   ┌──────────────────┐
                                   │ SQS + DLQ        │
                                   └────────┬─────────┘
                                            ▼
                                   ┌──────────────────┐
                                   │ Lambda fanout    │
                                   └───────┬──────────┘
                                           │
                ┌──────────────────────────┼──────────────────┐
                ▼                          ▼                  ▼
        WebSocket A                   WebSocket B        WebSocket C

                   AUTENTICACIÓN (solo si hay clientes reales)
   Cliente ──login→ Cognito/JWT ──JWT en $connect→ API GW WebSocket
                                                    │
                                                    ▼
                                   DynamoDB connections + TTL
```

Principio clave: **cálculo único → alerta única → fanout**. No se ejecuta el bot una vez por cliente. La suscripción decide quién *recibe*, no cuántas veces se *calcula*.

## 3. Stack de servicios

| Servicio | Función | Nota |
|---|---|---|
| S3 + CloudFront | Landing y dashboard (estático) | CloudFront opcional al inicio |
| Stripe Checkout | Pago | Fuera de AWS |
| API Gateway HTTP + Lambda | Webhook Stripe idempotente (verificar `Stripe-Signature`, dedup por `event.id`) | |
| DynamoDB on-demand | usuarios, plan, estado de suscripción (`trialing/active/past_due/canceled/unpaid`), conexiones WebSocket, dedup eventos Stripe | |
| **ECS Fargate** | **Runtime del bot, la pieza principal** | 1 task `0.25 vCPU / 0.5 GB`, x86 |
| EFS | Volumen persistente (SQLite/archivos) | Solo Fase 1 |
| SQS + DLQ | Cola de alertas; desacopla bot de entrega | |
| Lambda fanout | Distribuye alertas a conexiones WebSocket | |
| API Gateway WebSocket | Entrega en tiempo real | `$connect`, `$disconnect`, limpieza, TTL |
| Cognito / JWT | Autenticación de clientes | JWT corto, no API keys permanentes |
| Secrets Manager | Stripe, Binance Demo, APIs pagadas | 1 secret, nunca en código/DynamoDB |
| CloudWatch | Logs, métricas, alarmas | |
| ECR | Imágenes del contenedor | |
| CDK + GitHub Actions | Infra como código + CI/CD | OIDC, no credenciales AWS permanentes |

## 4. Correcciones a la propuesta original

1. **EventBridge no hace cron de 15 segundos.** Resolución de minutos. El bot no va en Lambda; va en Fargate continuo.
2. **API Key permanente NO vale para WebSocket.** Usar JWT corto; revocar en `customer.subscription.deleted` / `invoice.payment_failed` con `DeleteConnection`.
3. **"100% gratis" / "DynamoDB $0.00" / "solo milisegundos"** son afirmaciones incorrectas para la propuesta comercial. Free Tier no cubre Fargate ni IPv4 público.
4. **DynamoDB no reemplaza desk.db.** SQLite/PostgreSQL para datos relacionales; DynamoDB solo para suscripciones + conexiones + dedup.
5. **Vender alertas, no credenciales Binance propias.** El producto entrega decisiones; nunca expone tus claves ni las de los clientes.

## 5. Costos estimados (us-east-1, 730 h/mes)

### Escenario A — V1 lean, 10 usuarios (~$14-16/mes)

| Componente | Cálculo | Costo/mes |
|---|---|---|
| Fargate 0.25 vCPU | CPU $0.000011244/vCPU-s + mem $0.000001235/GB-s | $9.01 |
| IPv4 público del task | $0.005/h | $3.65 |
| EFS ~1 GB | $0.30/GB | $0.30 |
| CloudWatch Logs ~1 GB | ~$0.55 ingestión + $0.05 | $0.60 |
| ECR ~1 GB | | $0.10 |
| Secrets Manager (1 secret) | | $0.05 |
| API Gateway WebSocket | $1.00/M msgs, $0.25/M min conexión | ~$0.11 |
| Lambda (fanout + webhook) | $0.20/M req, $0.0000166667/GB-s | ~$0.001 |
| DynamoDB on-demand | $0.625/M write, $0.125/M read | ~$0.23 |
| SQS | 1M free | $0 |
| Cognito (10 MAU) | Free tier | $0 |
| S3/CloudFront | | ~$0.10 |
| **Total** | | **~$14-16** |

### Escenario B — Con RDS PostgreSQL (~$27-29/mes)

Escenario A + RDS `db.t4g.micro` $11.68 + 20 GB gp3 $2.30 = **$13.98**.

### Escenario 1 usuario (~$13-15/mes, NO recomendado)

Mismo casi fino: Fargate e infraestructura fija dominan. Para 1 usuario conviene Lightsail (~$5-7) o EC2 t4g.micro (~$10). AWS serverless con 1 usuario ≈ 47% de un ingreso de $30/mes.

### Costos excluidos (no olvidar)

- Stripe: ~2.9% + $0.30 por transacción.
- APIs pagadas de datos del bot.
- Dominio (~$12/año).
- Soporte AWS (opcional).
- Transferencia de salida si supera ~100 GB/mes free tier.

## 6. Fases de implementación

### Fase 1 — Validar con primeros clientes (5-10)

```text
Landing:        S3 + CloudFront (estática)
Pago:           Stripe Checkout
Webhook:        API Gateway HTTP + Lambda idempotente
Suscripciones:  DynamoDB on-demand
Runtime:        1 task ECS Fargate (0.25 vCPU / 0.5 GB)
Estado:         SQLite + EFS (temporal)
Cola:           SQS + DLQ
Entrega:        Lambda fanout + API Gateway WebSocket
Auth:           Cognito/JWT (JWT corto, validado en $connect)
Secretos:       Secrets Manager
Logs/alertas:   CloudWatch
Infra:          CDK + GitHub Actions (OIDC)
```

### Fase 2 — Producto validado

```text
SQLite+EFS → RDS PostgreSQL (datos del bot)
1 task → ECS service con deploy controlado
Dashboard local → CloudFront + API
Entitlements → planes y canales
Alarmas básicas en CloudWatch
WebSocket → canales adicionales (email/Telegram/push) opcional
```

### Fase 3 — Mayor escala (solo si la demanda lo justifica)

```text
Separar scanner / resolver / delivery
EventBridge para eventos internos (>= 1 min)
SQS por prioridad; fanout en lotes
RDS Proxy
Multi-AZ, WAF, rate limiting
Observabilidad por cliente
```

No construir Fase 3 hoy.

## 7. Detalles de implementación clave (checklist en código)

- [ ] `run_scheduler_loop.py` como `CMD` del contenedor. Estado en volumen (EFS/RDS), no en capa efímera.
- [ ] Puppy flags duplicados en Fargate: `BINANCE_DEMO_TRADING_ENABLED=true` Y `BINANCE_DEMO_ALLOW_ORDERS=true`.
- [ ] Endpoint guard del cliente Binance Demo (`demo|testnet` obligatorio) se mantiene.
- [ ] Agente publica a SQS con `eventId` único y `schemaVersion`. Deduplicación en consumo.
- [ ] WebSocket: `$connect` valida JWT, guarda `userId+connectionId+expiresAt` con TTL en DynamoDB; `$disconnect` limpia; `@connections` responde 410 → borrar.
- [ ] Webhook Stripe: verificar firma, dedup `event.id`, update entitlement, desconectar cancelados.
- [ ] Alerta JSON de ejemplo:

```json
{
  "eventId": "evt_01J...",
  "schemaVersion": 1,
  "type": "ENTRY_READY",
  "symbol": "BTCUSDT",
  "side": "LONG",
  "entry": 62000,
  "stop": 60800,
  "tp1": 63200,
  "tp2": 64100,
  "primaryTarget": 65000,
  "createdAt": "2026-08-28T18:30:00Z"
}
```

- [ ] Fargate en **subnet pública** para salir a Binance/APIs sin NAT Gateway (~$35/mes de ahorro). Sin ALB si no hay inbound (solo se empujan alertas).
- [ ] GitHub Actions con OIDC federado (jamás access keys de AWS en el repo).
- [ ] Verificar precios finales en AWS Calculator antes del primer deploy.

## 8. Pre-requisitos de producto ANTES de vender

1. Definir qué se vende: alertas, software o ejecución automática.
2. Dejar claro que rendimiento shadow != rendimiento real.
3. Importar fills/PnL real (`userTrades`/fills) antes de publicar estadísticas.
4. Deduplicar oportunidades correlacionadas en los rankings.
5. Términos, disclaimer financiero y política de privacidad.
6. Nunca exponer credenciales Binance propias ni operar con fondos de clientes.
7. Versionar el esquema de cada alerta.
8. Registrar entrega, no solo generación.
9. Definir latencia prometida y mantenimiento.
10. Separar entornos: Demo, staging, producción.

## 9. Conclusión

- **Uso personal/1 usuario: local, $0.** El plan AWS no aplica.
- **5-10 usuarios: esta arquitectura, ~$14-16/mes.**
- La pieza central es **Fargate**; serverless solo para comercial y entrega.
- Validar demanda con Fase 1 antes de migrar nada a RDS o escalar.