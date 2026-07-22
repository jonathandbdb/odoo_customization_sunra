# Customer Warranty Module for Odoo 19

<img src="static/description/images/variant_ss.png" alt="Warranty Management" width="800">

## Overview

**Customer Warranty** is a comprehensive warranty management module for Odoo 19 that enables businesses to track product warranties at multiple levels - from product categories to individual serial numbers. The module automatically calculates and manages warranty expiry dates based on customer delivery dates, making warranty tracking effortless and accurate.

## Key Features

### 📦 Multi-Level Warranty Configuration
- **Category Level**: Set default warranty terms for entire product categories
- **Product Template Level**: Override category settings with product-specific warranties
- **Product Variant Level**: Fine-tune warranty terms for individual product variants
- **Flexible Inheritance**: Each level can inherit from its parent or define custom warranty terms

### ⏰ Smart Warranty Calculation
The module supports three warranty start date types:
- **First Sale**: Warranty starts on the first customer delivery (ideal for products with long shelf life)
- **Last Sale**: Warranty resets with each customer delivery (useful for resold items)
- **Manufacturing**: Warranty starts from production date (perfect for perishable or time-sensitive products)

### 🔢 Serial Number Tracking
- Automatic warranty expiry date calculation for serialized products
- Warranty dates are automatically assigned when products are delivered to customers
- Smart handling of returns and re-sales
- View warranty status directly on serial number records

### 📊 Warranty Information Display
- **Effective Warranty** field shows the active warranty with its source (Category/Template/Variant)
- Clear visibility of warranty duration, unit (Days/Weeks/Months/Years), and start type
- Easy-to-understand warranty information at a glance

## Screenshots

### Product Category Warranty Configuration
<img src="static/description/images/kategori_ss.png" alt="Category Warranty Settings" width="600">

Set default warranty terms at the category level that automatically apply to all products in that category.

### Product Variant Warranty Management
<img src="static/description/images/variant_ss.png" alt="Variant Warranty Settings" width="600">

Configure warranty settings for individual product variants with the option to inherit from template or category, or set custom warranty terms.

### Warranty List View
<img src="static/description/images/garanti_listesi_ss.png" alt="Warranty List" width="600">

View all warranty information in a convenient list format with effective warranty details clearly displayed.

## Configuration

### Setting Up Category Warranties

1. Navigate to **Inventory > Configuration > Product Categories**
2. Select a category or create a new one
3. In the **Warranty** tab:
   - Set **Warranty Duration** (e.g., 24)
   - Choose **Warranty Unit** (Days/Weeks/Months/Years)
   - Select **Warranty Start Date** type (First Sale/Last Sale/Manufacturing)

### Configuring Product Warranties

1. Go to **Inventory > Products > Products**
2. Open a product or create a new one
3. In the **Warranty** tab:
   - Enable **Warranty Tracking** checkbox
   - Choose **Warranty Type**:
     - **Use Category Warranty**: Inherit from product category
     - **Custom Warranty**: Set product-specific warranty terms
   - If Custom is selected, configure duration, unit, and start type
   - View **Effective Warranty** to see the active warranty configuration

### Product Variant Warranties

For products with variants:
1. Open the product template
2. Click on **Variants** smart button
3. Select a variant
4. In the **Warranty** tab:
   - Enable **Warranty Tracking** (inherited from template by default)
   - Choose **Warranty Type**:
     - **Use Template Warranty**: Inherit from product template
     - **Use Category Warranty**: Inherit from product category
     - **Custom Warranty**: Set variant-specific warranty terms

## How It Works

### Warranty Start Type Behavior

- **First Sale**: Warranty date is set only on the first customer delivery. Subsequent sales don't change the warranty.
- **Last Sale**: Warranty date is updated with each customer delivery. Returns reset the warranty date.
- **Manufacturing**: Warranty date is set when the product exits production, regardless of customer delivery.

### Return Handling

When a product is returned from a customer:
- If warranty type is **Last Sale**, the warranty expiry date is cleared
- If warranty type is **First Sale** or **Manufacturing**, the warranty date remains unchanged

## Support & Contribution

- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/SalihKalender28/sk_customer_product_warranty/issues)
- **Contributions**: Pull requests are welcome!
- **Author**: Salih Kalender
- **Website**: [https://github.com/SalihKalender28](https://github.com/SalihKalender28)

## License

This module is licensed under LGPL-3. See LICENSE file for details.

---

**Note**: This module requires Odoo 19.0 and depends on the `product` and `stock` modules which are part of Odoo's core functionality.
