import { useEffect, useState } from "react";
import { Package, Trash2 } from "lucide-react";
import apiClient from "../services/api";

export default function Products() {

  const [products, setProducts] = useState([]);

  const [formData, setFormData] = useState({
    name: "",
    sku: "",
    description: "",
    category: "",
    current_price: "",
    cost_price: "",
    inventory_quantity: "",
    min_margin_percentage: "10",
  });

  const fetchProducts = async () => {
    try {

      const response = await apiClient.get("/products");

      setProducts(
        response.data.products || []
      );

    } catch (error) {

      console.error(error);

    }
  };

  useEffect(() => {

    fetchProducts();

  }, []);

  const handleChange = (e) => {

    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });

  };

  const handleCreateProduct = async (e) => {

    e.preventDefault();

    try {

      await apiClient.post("/products", {
        ...formData,
        current_price: Number(formData.current_price),
        cost_price: Number(formData.cost_price),
        inventory_quantity: Number(formData.inventory_quantity),
        min_margin_percentage: Number(formData.min_margin_percentage),
      });

      setFormData({
        name: "",
        sku: "",
        description: "",
        category: "",
        current_price: "",
        cost_price: "",
        inventory_quantity: "",
        min_margin_percentage: "10",
      });

      fetchProducts();

    } catch (error) {

      console.error(error);

      alert("Failed to create product");

    }
  };

  const handleDelete = async (id) => {

    try {

      await apiClient.delete(`/products/${id}`);

      fetchProducts();

    } catch (error) {

      console.error(error);

    }
  };

  return (
    <div className="p-8 text-white">

      <h1 className="text-4xl font-bold mb-8">
        Products
      </h1>

      <form
        onSubmit={handleCreateProduct}
        className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10"
      >

        <input
          type="text"
          name="name"
          placeholder="Product Name"
          value={formData.name}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <input
          type="text"
          name="sku"
          placeholder="SKU"
          value={formData.sku}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <input
          type="text"
          name="category"
          placeholder="Category"
          value={formData.category}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <input
          type="number"
          name="current_price"
          placeholder="Current Price"
          value={formData.current_price}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <input
          type="number"
          name="cost_price"
          placeholder="Cost Price"
          value={formData.cost_price}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <input
          type="number"
          name="inventory_quantity"
          placeholder="Inventory"
          value={formData.inventory_quantity}
          onChange={handleChange}
          required
          className="bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <textarea
          name="description"
          placeholder="Description"
          value={formData.description}
          onChange={handleChange}
          className="md:col-span-2 bg-slate-900 border border-white/10 rounded-xl px-4 py-3"
        />

        <button
          type="submit"
          className="md:col-span-2 bg-violet-600 hover:bg-violet-700 rounded-xl py-4 font-semibold"
        >
          Create Product
        </button>

      </form>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {products.map((product) => (

          <div
            key={product.id}
            className="bg-slate-900 border border-white/10 rounded-3xl p-6"
          >

            <div className="flex items-center justify-between mb-6">

              <div className="w-14 h-14 rounded-2xl bg-violet-500/20 flex items-center justify-center text-violet-400">
                <Package />
              </div>

              <button
                onClick={() => handleDelete(product.id)}
                className="text-red-400"
              >
                <Trash2 />
              </button>

            </div>

            <h2 className="text-2xl font-semibold mb-2">
              {product.name}
            </h2>

            <p className="text-slate-400 mb-4">
              {product.description}
            </p>

            <div className="space-y-2 text-sm">

              <div className="flex justify-between">
                <span>SKU</span>
                <span>{product.sku}</span>
              </div>

              <div className="flex justify-between">
                <span>Price</span>
                <span>₹{product.current_price}</span>
              </div>

              <div className="flex justify-between">
                <span>Inventory</span>
                <span>{product.inventory_quantity}</span>
              </div>

            </div>

          </div>

        ))}

      </div>

    </div>
  );
}