# Formatos suportados

Os adapters integrados são **compatíveis com exportações observadas** nas centrais de vendedores das plataformas listadas abaixo. Eles não representam uma especificação oficial das plataformas, que podem alterar nomes de colunas sem aviso prévio.

Antes da comparação com cada adapter, todos os cabeçalhos passam por normalização (minúsculas, remoção de acentos, substituição de pontuação por espaços e remoção de espaços excedentes).

## Shopee (`shopee`)

- **Tipo de relatório:** Relatório de pedidos
- **Data da observação:** `2026-11-22`
- **Compatibilidade:** Exportações da Central do Vendedor em português, inglês e espanhol.

### Colunas aceitas

| Campo canônico | Obrigatório | Aliases observados (PT / EN / ES) |
|---|---|---|
| `order_date` | Sim | `Data de criação do pedido`, `Hora de criação do pedido`, `Data do pedido`, `Order Creation Date`, `Order Date`, `Fecha de creación del pedido`, `Hora de creación del pedido`, `Fecha del pedido` |
| `product_name` | Sim | `Nome do Produto`, `Nome do item`, `Product Name`, `Item Name`, `Nombre del producto`, `Nombre del artículo` |
| `quantity` | Sim | `Quantidade`, `Quantidade do produto`, `Quantity`, `Cantidad` |
| `gross_revenue` | Sim | `Valor total do pedido`, `Subtotal do produto`, `Preço total`, `Total Order Amount`, `Product Subtotal`, `Grand Total`, `Monto total del pedido`, `Precio total`, `Subtotal del producto` |
| `order_id` | Não | `ID do pedido`, `Número do pedido`, `Order ID`, `ID de pedido`, `Número de pedido` |
| `status` | Não | `Status do pedido`, `Order Status`, `Estado del pedido` |
| `sku` | Não | `Número de referência SKU`, `SKU do Produto`, `SKU principal`, `SKU Reference No.`, `SKU Reference No`, `Parent SKU Reference No.`, `Parent SKU`, `SKU de referencia`, `N.º de referencia de SKU`, `SKU` |
| `unit_price` | Não | `Preço acordado`, `Preço com desconto`, `Preço original`, `Preço unitário`, `Deal Price`, `Original Price`, `Unit Price`, `Precio de oferta`, `Precio original`, `Precio unitario` |
| `fees` | Não | `Taxa de comissão`, `Taxa de serviço`, `Taxa de transação`, `Commission Fee`, `Service Fee`, `Transaction Fee`, `Tarifa de comisión`, `Tarifa de servicio`, `Comisión` |
| `shipping_cost` | Não | `Taxa de envio paga pelo comprador`, `Taxa de envio estimada`, `Custo de envio`, `Frete`, `Buyer Paid Shipping Fee`, `Estimated Shipping Fee`, `Shipping Fee`, `Tarifa de envío pagada por el comprador`, `Costo de envío` |

### Status mapeados

- `concluido`: `Concluído`, `Entregue`, `Completed`, `Completado`
- `cancelado`: `Cancelado`, `Cancelled`, `Canceled`
- `devolvido`: `Devolução/Reembolso`, `Devolvido`, `Reembolsado`, `Return/Refund`, `Returned`, `Devolución/Reembolso`, `Devuelto`
- `em_andamento`: `A enviar`, `Pronto para envio`, `Enviado`, `Não pago`, `A pagar`, `A caminho`, `Unpaid`, `To Ship`, `Ready to Ship`, `Shipping`, `Shipped`, `Por enviar`, `Pendiente de pago`, `En camino`

## Mercado Livre (`mercado_livre`)

- **Tipo de relatório:** Relatório de vendas
- **Data da observação:** `2026-11-22`
- **Compatibilidade:** Exportações de vendas do Mercado Livre e Mercado Libre em português, espanhol e inglês.

### Colunas aceitas

| Campo canônico | Obrigatório | Aliases observados (PT / ES / EN) |
|---|---|---|
| `order_date` | Sim | `Data da venda`, `Fecha de venta`, `Sale Date` |
| `product_name` | Sim | `Título do anúncio`, `Título de la publicación`, `Listing Title`, `Item Title` |
| `quantity` | Sim | `Unidades`, `Units` |
| `gross_revenue` | Sim | `Receita por produtos`, `Receita por produtos (BRL)`, `Valor do produto`, `Ingresos por productos`, `Valor del producto`, `Monto total`, `Product Revenue`, `Revenue` |
| `order_id` | Não | `N.º de venda`, `Nº de venda`, `N° de venda`, `Número da venda`, `ID da venda`, `N.º de venta`, `Nº de venta`, `N° de venta`, `Número de venta`, `ID de venta`, `Sale Number`, `Order Number` |
| `status` | Não | `Estado`, `Status da venda`, `Estado de la venta`, `Status`, `Sale Status` |
| `sku` | Não | `SKU`, `Código SKU` |
| `unit_price` | Não | `Preço unitário de venda do anúncio`, `Preço unitário`, `Precio unitario de venta de la publicación`, `Precio unitario`, `Unit Price` |
| `fees` | Não | `Tarifa de venda e impostos`, `Tarifa de venda`, `Tarifa`, `Cargo por venta e impuestos`, `Cargo por venta`, `Comisión`, `Selling Fee and Taxes`, `Selling Fee` |
| `shipping_cost` | Não | `Tarifas de envio`, `Tarifa de envio`, `Custo de envio`, `Costos de envío`, `Tarifas de envío`, `Costo de envío`, `Shipping Cost`, `Shipping Fee` |
| `net_revenue` | Não | `Total (BRL)`, `Valor líquido`, `Total líquido`, `Total`, `Monto recibido`, `Monto neto`, `Net Revenue`, `Total Received` |

### Status mapeados

- `concluido`: `Entregue`, `Venda entregue`, `Concluída`, `Concluído`, `Acreditada`, `Entregada`, `Completada`, `Pagada`, `Delivered`, `Completed`
- `cancelado`: `Cancelada`, `Cancelado`, `Cancelada pelo comprador`, `Cancelada pelo vendedor`, `Anulada`, `Cancelled`, `Canceled`
- `devolvido`: `Devolvida`, `Devolvido`, `Em devolução`, `Devuelta`, `En devolución`, `Reembolsada`, `Returned`, `Refunded`
- `em_andamento`: `A combinar`, `A caminho`, `Em trânsito`, `Em preparação`, `Etiqueta pronta`, `Pendente`, `En camino`, `En preparación`, `Pendiente`, `In Transit`, `Pending`, `Processing`

## Modo CSV/XLSX genérico (`generico`)

Qualquer planilha `.csv` ou `.xlsx` que não siga um formato conhecido pode ser utilizada no modo genérico por meio do mapeamento manual de colunas. Esse modo funciona de maneira independente dos adapters acima e exige apenas data, produto, quantidade e um campo de valor (`gross_revenue` ou `unit_price`).
