import os
import json
import uuid
from decimal import Decimal
from dotenv import load_dotenv
from fastmcp import FastMCP
from supabase import create_client
import stripe

load_dotenv()

mcp = FastMCP("BIU_eCommerce Assistant")

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)

PROMPT_PANTALLA_PAGO = """
Crea una pantalla web de pago para un pedido de comercio electrónico.

La pantalla debe contener:

- Nombre de la tienda: TechStore
- Número de pedido
- Resumen de productos
- Subtotal
- Impuesto
- Total
- Nombre del titular
- Número de tarjeta
- Fecha de vencimiento
- CVV
- Botón Pagar pedido
- Botón Cancelar
- Mensaje de seguridad

Diseño:

- Interfaz moderna y responsive.
- Fondo claro.
- Tarjeta de pago centrada.
- Resumen del pedido en una columna.
- Formulario de pago en otra columna.
- Colores azul, blanco y gris.
- No mostrar ni almacenar datos después de completar el pago.
- Utilizar datos simulados exclusivamente para la práctica.
- Mostrar una advertencia:
  "Esta es una pantalla académica de demostración. No ingrese datos reales."

La página debe permitir validar campos, pero no debe conectarse a una entidad bancaria.
"""

@mcp.tool
def buscar_productos(
    texto: str = "",
    categoria: str = "",
    precio_minimo: float = 0,
    precio_maximo: float = 999999,
    limite: int = 10
) -> dict:
    """
    Busca productos por nombre, categoría y rango de precios.
    Devuelve nombre, precio, stock, características e imagen.
    """

    consulta = (
        supabase.table("productos")
        .select("*")
        .eq("activo", True)
        .gte("precio", precio_minimo)
        .lte("precio", precio_maximo)
        .limit(limite)
    )

    if categoria:
        consulta = consulta.ilike("categoria", f"%{categoria}%")

    if texto:
        consulta = consulta.ilike("nombre", f"%{texto}%")

    resultado = consulta.execute()

    return {
        "total": len(resultado.data),
        "productos": resultado.data
    }


@mcp.tool
def obtener_producto(producto_id: int) -> dict:
    """Obtiene la información completa de un producto."""

    resultado = (
        supabase.table("productos")
        .select("*")
        .eq("id", producto_id)
        .single()
        .execute()
    )

    return resultado.data


@mcp.tool
def crear_carrito(cliente_id: str | None = None) -> dict:
    """Crea un carrito activo."""

    resultado = (
        supabase.table("carritos")
        .insert({
            "cliente_id": cliente_id,
            "estado": "activo"
        })
        .execute()
    )

    return resultado.data[0]


@mcp.tool
def agregar_al_carrito(
    carrito_id: str,
    producto_id: int,
    cantidad: int
) -> dict:
    """Agrega un producto al carrito validando el stock."""

    producto = (
        supabase.table("productos")
        .select("*")
        .eq("id", producto_id)
        .single()
        .execute()
    ).data

    if not producto:
        return {"error": "Producto no encontrado"}

    if producto["stock"] < cantidad:
        return {
            "error": "Stock insuficiente",
            "stock_disponible": producto["stock"]
        }

    item = (
        supabase.table("carrito_items")
        .upsert({
            "carrito_id": carrito_id,
            "producto_id": producto_id,
            "cantidad": cantidad,
            "precio_unitario": producto["precio"]
        })
        .execute()
    )

    return {
        "mensaje": "Producto agregado al carrito",
        "item": item.data[0]
    }


@mcp.tool
def ver_carrito(carrito_id: str) -> dict:
    """Muestra los productos del carrito y calcula el total."""

    items = (
        supabase.table("carrito_items")
        .select("*, productos(*)")
        .eq("carrito_id", carrito_id)
        .execute()
    ).data

    subtotal = Decimal("0")

    resultado = []

    for item in items:
        cantidad = item["cantidad"]
        precio = Decimal(str(item["precio_unitario"]))
        total_item = precio * cantidad
        subtotal += total_item

        resultado.append({
            "producto": item["productos"]["nombre"],
            "imagen_url": item["productos"]["imagen_url"],
            "cantidad": cantidad,
            "precio_unitario": float(precio),
            "subtotal": float(total_item)
        })

    impuesto = subtotal * Decimal("0.15")
    total = subtotal + impuesto

    return {
        "carrito_id": carrito_id,
        "items": resultado,
        "subtotal": float(subtotal),
        "impuesto": float(impuesto),
        "total": float(total),
        "moneda": "USD"
    }

@mcp.tool
def crear_pedido(
    carrito_id: str,
    cliente_id: str,
    direccion_entrega: str
) -> dict:
    """Convierte un carrito activo en un pedido."""

    carrito = ver_carrito(carrito_id)

    if not carrito["items"]:
        return {"error": "El carrito está vacío"}

    numero_pedido = f"PED-{uuid.uuid4().hex[:10].upper()}"

    pedido = (
        supabase.table("pedidos")
        .insert({
            "cliente_id": cliente_id,
            "carrito_id": carrito_id,
            "numero_pedido": numero_pedido,
            "estado": "pago_pendiente",
            "subtotal": carrito["subtotal"],
            "impuesto": carrito["impuesto"],
            "total": carrito["total"]
        })
        .execute()
    ).data[0]

    return {
        "mensaje": "Pedido creado correctamente",
        "pedido_id": pedido["id"],
        "numero_pedido": numero_pedido,
        "total": carrito["total"],
        "direccion_entrega": direccion_entrega,
        "estado": "pago_pendiente"
    }

@mcp.tool
def preparar_pantalla_pago(pedido_id: str) -> dict:
    """
    Prepara una pantalla académica de pago utilizando un prompt fijo.
    No procesa pagos reales.
    """

    pedido = (
        supabase
        .table("pedidos")
        .select("*")
        .eq("id", pedido_id)
        .single()
        .execute()
    ).data

    if not pedido:
        return {
            "error": "Pedido no encontrado"
        }

    items = (
        supabase
        .table("pedido_items")
        .select("*")
        .eq("pedido_id", pedido_id)
        .execute()
    ).data

    token_pago = str(uuid.uuid4())

    return {
        "tipo": "pantalla_pago_academica",
        "pedido_id": pedido["id"],
        "numero_pedido": pedido["numero_pedido"],
        "subtotal": pedido["subtotal"],
        "impuesto": pedido["impuesto"],
        "total": pedido["total"],
        "moneda": "USD",
        "items": items,
        "token_pago": token_pago,
        "ruta_frontend": f"/pago/{pedido['id']}",
        "prompt_diseno": PROMPT_PANTALLA_PAGO,
        "advertencia": (
            "Esta pantalla es únicamente académica. "
            "No ingresar datos reales de tarjetas."
        )
    }

@mcp.prompt
def prompt_pantalla_pago(pedido_id: str) -> str:
    return f"""
Diseña una pantalla responsive para pagar el pedido {pedido_id}.

Utiliza la siguiente estructura:

{PROMPT_PANTALLA_PAGO}

La página debe recibir los datos del pedido desde el backend y mostrar:

- Productos
- Cantidades
- Subtotal
- Impuesto
- Total
- Formulario de tarjeta de demostración

Cuando el usuario presione "Pagar pedido":

1. Validar que los campos estén completos.
2. Mostrar un mensaje de procesamiento.
3. Actualizar el pedido a estado "pagado_simulado".
4. Registrar la operación en la tabla pagos.
5. Limpiar los campos de tarjeta.
6. Mostrar el número de pedido y el comprobante.

No almacenar números de tarjeta, CVV ni fechas de vencimiento.
"""

@mcp.tool
def confirmar_pago_simulado(
    pedido_id: str,
    nombre_titular: str,
    numero_tarjeta: str,
    fecha_vencimiento: str,
    cvv: str
) -> dict:
    """
    Simula la confirmación de un pago.
    Nunca almacena los datos de la tarjeta.
    """

    if not nombre_titular.strip():
        return {"error": "El nombre del titular es obligatorio"}

    if len(numero_tarjeta.replace(" ", "")) != 16:
        return {"error": "El número de tarjeta debe tener 16 dígitos"}

    if len(cvv) not in [3, 4]:
        return {"error": "El CVV no es válido"}

    pedido = (
        supabase
        .table("pedidos")
        .select("*")
        .eq("id", pedido_id)
        .single()
        .execute()
    ).data

    if not pedido:
        return {"error": "Pedido no encontrado"}

    # Nunca se guardan numero_tarjeta, fecha_vencimiento ni cvv
    supabase.table("pedidos").update({
        "estado": "pagado_simulado"
    }).eq("id", pedido_id).execute()

    supabase.table("pagos").insert({
        "pedido_id": pedido_id,
        "proveedor": "simulado",
        "referencia_externa": f"SIM-{uuid.uuid4().hex[:10].upper()}",
        "estado": "pagado_simulado",
        "monto": pedido["total"],
        "moneda": "usd"
    }).execute()

    return {
        "mensaje": "Pago simulado aprobado",
        "pedido_id": pedido_id,
        "numero_pedido": pedido["numero_pedido"],
        "total": pedido["total"],
        "estado": "pagado_simulado",
        "datos_tarjeta_eliminados": True
    }

@mcp.prompt
def asistente_compras() -> str:
    return """
Eres un asistente de compras de una tienda tecnológica.

Usa buscar_productos para consultar el catálogo.
Usa agregar_al_carrito para agregar productos.
Usa ver_carrito para mostrar el carrito.
Usa crear_pedido después de solicitar confirmación.
Usa preparar_pantalla_pago cuando el cliente desee pagar.
Usa confirmar_pago_simulado después del pago académico.

No solicites datos de tarjetas dentro del chat.
No almacenes números de tarjeta, CVV ni fechas de vencimiento.
Indica siempre que la pantalla de pago es una demostración académica.
"""

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )