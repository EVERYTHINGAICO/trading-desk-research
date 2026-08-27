# El sistema explicado para ninos

## Que es

Imagina un robot que observa un enorme tablero de precios. No adivina el futuro como un mago. Mira datos, hace cuentas y sigue reglas.

El sistema tiene dos trabajos distintos:

1. Mirar el mercado y decir que oportunidades parecen interesantes.
2. Si se habilita la parte Demo, mandar ordenes de prueba a Binance Futures Demo.

## Como mira el mercado

Cada cierto tiempo pregunta a Binance:

- cual es el precio;
- cuanto subio o bajo;
- cuanto se negocio;
- como fueron las velas recientes;
- como esta BTC;
- algunos datos de futuros.

Una vela es como una cajita que resume lo que paso durante 15 minutos: donde comenzo el precio, hasta donde subio, hasta donde bajo y donde termino.

El robot no usa la vela que aun esta formandose. Espera a que cierre para no tomar decisiones sobre informacion incompleta.

## Las cuentas matematicas

Calcula lineas y medidas para entender el comportamiento:

- **EMA:** una linea que ayuda a ver la direccion de los precios.
- **Bollinger:** una banda que muestra si el precio esta muy separado de lo normal.
- **MACD:** una medida de la velocidad y cambio del movimiento.
- **RSI:** indica si el movimiento reciente fue muy fuerte hacia arriba o hacia abajo.
- **VWAP:** un precio promedio tomando en cuenta cuanto se negocio.
- **ATR:** mide cuanto suele moverse el precio.

Estas cuentas no votan como personas. Son piezas de evidencia. El robot las guarda para que podamos revisar que vio.

## Que busca

Busca cosas como estas:

```text
el precio baja fuerte
-> aparece mucho volumen
-> el precio intenta recuperar una zona
-> la estructura parece sostenerse
-> se prepara un plan
```

Tiene varios nombres para distintos dibujos del mercado:

- una capitulacion que recupera;
- una capitulacion que apenas empieza a recuperarse;
- una ruptura falsa que vuelve a subir;
- una ruptura que vuelve a probar una zona y aguanta;
- un retroceso dentro de una tendencia;
- un rebote que todavia necesita mas pruebas.

Son nombres para describir formas distintas. El sistema actual ejecuta la parte Binance principalmente para operaciones long, es decir, esperando que el precio suba.

## Los estados son como semaforos

Cada oportunidad tiene un estado:

- **PASS:** no cumple lo suficiente.
- **WATCH:** la observamos.
- **PRE-ENTRY:** se acerca, pero aun no es momento.
- **ENTRY_READY:** el plan esta listo para revisar o replicar.
- **MISSED:** ya se fue demasiado lejos; no hay que perseguirlo.
- **INVALIDATED:** la idea dejo de tener sentido.

`ENTRY_READY` no significa que una orden ya se lleno. Solo significa que la oportunidad paso los filtros del robot.

## El plan de una operacion

Antes de considerar una operacion, el sistema guarda:

- entrada;
- nivel donde la idea deja de ser valida;
- stop loss;
- TP1;
- TP2;
- objetivo principal;
- relacion riesgo/beneficio;
- tipo de trigger.

Es como escribir las reglas de un juego antes de empezar. Despues no se cambian para fingir que el resultado fue mejor.

## Como decide el score

El robot empieza con una puntuacion y agrega puntos cuando encuentra evidencia:

- una caida suficiente;
- volumen fuerte;
- rebote;
- buena calidad de datos;
- precio en una zona importante;
- BTC ayudando.

Tambien quita puntos cuando BTC esta debil o faltan datos.

El score no es una probabilidad garantizada. Solo es una forma ordenada de comparar candidatos.

## Que hace BTC

BTC es como el clima general para muchas monedas. Si BTC esta fuerte en varios periodos, puede ayudar a una idea de otra moneda. Si BTC pierde fuerza, el robot es mas cuidadoso.

Mira BTC en 15 minutos, 1 hora, 4 horas y 1 dia, y compara el precio con una linea llamada EMA20.

## Que hace el AI

El AI no deberia inventar numeros ni mover el plan. Su trabajo previsto es leer el contexto:

- noticias;
- eventos importantes;
- contradicciones;
- contexto macro;
- explicaciones.

El codigo determinista conserva la autoridad sobre precios, indicadores, stop, objetivos y estados.

En la version actual, el paquete para AI existe, pero el scanner Python no llama automaticamente al modelo ni a busqueda web. Cuando esa conexion no existe, escribe `N/A` y una recomendacion conservadora.

## Que pasa en Binance Demo

La parte Demo es otra capa. Solo trabaja si se encienden dos permisos especiales.

Para la ejecucion actual:

```text
señal lista
-> orden BUY LIMIT
-> esperar hasta 30 segundos
-> si no llena, queda SUBMITTED y sigue abierta para vigilancia
-> si llena, crear SL y TP nativos
-> confirmar protecciones
-> PROTECTED
```

La posicion usa One-way y margen aislado 1x. La orden nativa de stop y la de objetivo principal protegen la posicion agregada de ese simbolo.

## Que pasa si Binance no puede poner el stop

A veces Binance puede decir que ya hay demasiadas ordenes stop. Ese error se conoce como `-4045`.

El sistema entonces debe entender:

```text
la entrada si se ejecuto
pero la proteccion no pudo crearse
```

Por eso existe un watcher de respaldo. Revisa cada 15 segundos si hay una posicion sin proteccion completa. Si el precio llega al stop o al objetivo, puede enviar una orden de mercado para reducir la posicion:

- long: vender;
- short: comprar.

El watcher guarda lo que hizo en la base de datos y puede avisar por Telegram.

En este momento las posiciones que estaban sin proteccion fueron cerradas durante la limpieza autorizada, y las posiciones restantes revisadas tienen proteccion nativa completa.

## Como recuerda todo

La base SQLite es como el cuaderno central del robot. Guarda:

- oportunidades;
- planes;
- cambios de estado;
- ordenes;
- fills;
- posiciones;
- stops y objetivos;
- errores;
- reconciliaciones;
- acciones del watcher;
- entregas de Telegram.

Tambien hay archivos de eventos y diarios para leer la historia, pero SQLite es el registro central operativo.

## Que hace el scheduler

El scheduler es el reloj del sistema. Despierta los programas en distintos momentos:

- escaneo amplio cada hora;
- monitores de shadow cada 5 minutos;
- executor Demo cada 5 minutos;
- monitor, reconciliador y watcher cada 15 segundos.

Usa un archivo lock para impedir que dos relojes escriban en la misma base al mismo tiempo.

## Que muestra el dashboard

El dashboard es una ventana de solo lectura. No deberia cambiar la estrategia. Sirve para ver:

- si el sistema esta trabajando;
- cuantas oportunidades hay;
- que ordenes esperan fill;
- que posiciones estan abiertas;
- cuales tienen proteccion;
- que errores necesitan atencion;
- que paso recientemente.

La mejora ideal es usar palabras claras, por ejemplo:

```text
SUBMITTED = esperando entrada
FILLED = entrada ejecutada
PROTECTED = stop y objetivo confirmados
PROTECTION_REQUIRED = entrada ejecutada, falta proteccion
```

## Lo que el PDF pide y lo que falta

El documento de autoridad describe un desk mas grande que la version actual. Pide:

- long y short;
- varios tipos de tareas;
- noticias y macro conectadas;
- WebSocket;
- mas datos de derivados;
- dashboard por estrategia;
- metricas completas;
- replay y backtest.

El bot actual ya tiene una buena base para observar y calcular, pero todavia no implementa todo ese sistema grande. Sobre todo, la ejecucion actual es long-only y el AI/web aun no esta conectado automaticamente al scanner.

## Resumen en una frase

Es un robot que mira precios cerrados, hace cuentas, clasifica dibujos del mercado, escribe un plan sin cambiarlo despues, y opcionalmente prueba ordenes en Binance Demo con protecciones y vigilancia adicional.
