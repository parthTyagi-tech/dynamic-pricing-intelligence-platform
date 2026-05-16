import { useEffect, useState } from "react";

import {
  Package,
  Trash2,
  Plus,
  Boxes,
  DollarSign,
  Tag,
} from "lucide-react";

import { motion } from "framer-motion";

import apiClient from "../services/api";

export default function Products() {

  const [products, setProducts] = useState([]);

  const [loading, setLoading] = useState(false);

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

      setLoading(true);

      const response =
        await apiClient.get("/products");

      setProducts(
        response.data.products || []
      );

    } catch (error) {

      console.error(error);

    } finally {

      setLoading(false);
    }
  };

  useEffect(() => {

    fetchProducts();

  }, []);

  const handleChange = (e) => {

    setFormData({
      ...formData,
      [e.target.name]:
        e.target.value,
    });
  };

  const handleCreateProduct = async (e) => {

    e.preventDefault();

    try {

      await apiClient.post("/products", {

        ...formData,

        current_price:
          Number(formData.current_price),

        cost_price:
          Number(formData.cost_price),

        inventory_quantity:
          Number(formData.inventory_quantity),

        min_margin_percentage:
          Number(formData.min_margin_percentage),
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

      await apiClient.delete(
        `/products/${id}`
      );

      fetchProducts();

    } catch (error) {

      console.error(error);
    }
  };

  return (

    <div className="space-y-8">

      {/* HERO */}

      <div
        className="relative overflow-hidden rounded-[28px] border border-white/10 p-8 lg:p-10"
        style={{
          background:
            "linear-gradient(135deg,rgba(12,16,32,0.92),rgba(15,23,42,0.92))",

          boxShadow:
            "0 24px 60px rgba(0,0,0,0.35)",
        }}
      >

        <div
          style={{
            position: "absolute",
            width: 240,
            height: 240,
            borderRadius: "50%",
            background:
              "rgba(0,161,155,0.12)",

            filter: "blur(100px)",

            top: -60,
            right: -60,
          }}
        />

        <div className="relative z-10">

          <div className="inline-flex items-center gap-2 bg-[#00A19B]/10 border border-[#00A19B]/20 text-[#7FF6EE] px-4 py-2 rounded-full text-sm mb-6">

            <Boxes size={16} />

            Product Management Center

          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">

            <div>

              <h1 className="text-4xl lg:text-5xl font-bold text-white leading-tight">

                Product Inventory

              </h1>

              <p className="text-slate-400 text-lg mt-4 max-w-2xl leading-8">

                Manage products, inventory, pricing and marketplace
                catalog data inside your intelligent pricing workspace.

              </p>

            </div>

            <div className="grid grid-cols-2 gap-4 min-w-[280px]">

              <MiniStat
                title="Total Products"
                value={products.length}
              />

              <MiniStat
                title="Inventory Units"
                value={
                  products.reduce(
                    (acc, item) =>
                      acc +
                      item.inventory_quantity,
                    0
                  ) || 0
                }
              />

              <MiniStat
                title="Categories"
                value={
                  new Set(
                    products.map(
                      (p) => p.category
                    )
                  ).size
                }
              />

              <MiniStat
                title="Live Pricing"
                value="Active"
              />

            </div>

          </div>

        </div>

      </div>

      {/* CREATE PRODUCT */}

      <div className="glass-card p-7 lg:p-8">

        <div className="flex items-center gap-3 mb-8">

          <Plus className="text-[#00A19B]" />

          <h2 className="text-3xl font-bold text-white">

            Add New Product

          </h2>

        </div>

        <form
          onSubmit={handleCreateProduct}
          className="grid grid-cols-1 md:grid-cols-2 gap-5"
        >

          <InputField
            name="name"
            placeholder="Product Name"
            value={formData.name}
            onChange={handleChange}
          />

          <InputField
            name="sku"
            placeholder="SKU"
            value={formData.sku}
            onChange={handleChange}
          />

          <InputField
            name="category"
            placeholder="Category"
            value={formData.category}
            onChange={handleChange}
          />

          <InputField
            name="current_price"
            type="number"
            placeholder="Current Price"
            value={formData.current_price}
            onChange={handleChange}
          />

          <InputField
            name="cost_price"
            type="number"
            placeholder="Cost Price"
            value={formData.cost_price}
            onChange={handleChange}
          />

          <InputField
            name="inventory_quantity"
            type="number"
            placeholder="Inventory Quantity"
            value={formData.inventory_quantity}
            onChange={handleChange}
          />

          <textarea
            name="description"
            placeholder="Product Description"

            value={formData.description}

            onChange={handleChange}

            className="
              md:col-span-2
              h-32
              rounded-2xl
              bg-white/5
              border
              border-white/10
              px-5
              py-4
              text-white
              placeholder-slate-500
              outline-none
              focus:border-[#00A19B]
              transition-all
              resize-none
            "
          />

          <button
            type="submit"

            className="
              md:col-span-2
              rounded-2xl
              py-4
              text-white
              font-semibold
              transition-all
              hover:opacity-90
            "

            style={{
              background:
                "linear-gradient(135deg,#00A19B,#6366f1)",
            }}
          >

            Create Product

          </button>

        </form>

      </div>

      {/* PRODUCTS GRID */}

      <div className="space-y-6">

        <div className="flex items-center justify-between flex-wrap gap-4">

          <div>

            <h2 className="text-3xl font-bold text-white">

              Product Catalog

            </h2>

            <p className="text-slate-400 mt-2">

              Live inventory and pricing overview

            </p>

          </div>

        </div>

        {loading ? (

          <div className="glass-card p-10 text-center text-slate-400">

            Loading products...

          </div>

        ) : products.length === 0 ? (

          <div className="glass-card p-10 text-center">

            <Package
              size={48}
              className="mx-auto text-slate-600 mb-5"
            />

            <h3 className="text-xl font-semibold text-white mb-2">

              No Products Found

            </h3>

            <p className="text-slate-400">

              Create your first product to begin tracking pricing intelligence.

            </p>

          </div>

        ) : (

          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">

            {products.map((product) => (

              <motion.div
                key={product.id}

                whileHover={{
                  y: -5,
                }}

                className="
                  relative
                  overflow-hidden
                  rounded-3xl
                  border
                  border-white/10
                  bg-[rgba(17,24,39,0.78)]
                  p-6
                  backdrop-blur-xl
                "
              >

                <div
                  style={{
                    position: "absolute",
                    width: 140,
                    height: 140,
                    borderRadius: "50%",

                    background:
                      "rgba(0,161,155,0.08)",

                    filter: "blur(70px)",

                    top: -40,
                    right: -40,
                  }}
                />

                <div className="relative z-10">

                  <div className="flex items-center justify-between mb-6">

                    <div
                      className="
                        w-14
                        h-14
                        rounded-2xl
                        flex
                        items-center
                        justify-center
                        text-white
                      "
                      style={{
                        background:
                          "linear-gradient(135deg,#00A19B,#6366f1)",
                      }}
                    >

                      <Package size={24} />

                    </div>

                    <button
                      onClick={() =>
                        handleDelete(
                          product.id
                        )
                      }

                      className="
                        w-10
                        h-10
                        rounded-xl
                        flex
                        items-center
                        justify-center
                        text-red-400
                        hover:bg-red-500/10
                        transition-all
                      "
                    >

                      <Trash2 size={18} />

                    </button>

                  </div>

                  <div className="mb-6">

                    <h3 className="text-2xl font-semibold text-white mb-2">

                      {product.name}

                    </h3>

                    <p className="text-slate-400 leading-7 text-sm">

                      {product.description ||
                        "No description provided."}

                    </p>

                  </div>

                  <div className="space-y-4 text-sm">

                    <InfoRow
                      icon={Tag}
                      label="SKU"
                      value={product.sku}
                    />

                    <InfoRow
                      icon={DollarSign}
                      label="Price"
                      value={`₹${product.current_price}`}
                    />

                    <InfoRow
                      icon={Boxes}
                      label="Inventory"
                      value={
                        product.inventory_quantity
                      }
                    />

                    <InfoRow
                      icon={Package}
                      label="Category"
                      value={product.category}
                    />

                  </div>

                </div>

              </motion.div>
            ))}

          </div>
        )}

      </div>

    </div>
  );
}

function InputField({
  name,
  type = "text",
  placeholder,
  value,
  onChange,
}) {

  return (

    <input
      type={type}

      name={name}

      placeholder={placeholder}

      value={value}

      onChange={onChange}

      required

      className="
        h-14
        rounded-2xl
        bg-white/5
        border
        border-white/10
        px-5
        text-white
        placeholder-slate-500
        outline-none
        focus:border-[#00A19B]
        transition-all
      "
    />
  );
}

function MiniStat({
  title,
  value,
}) {

  return (

    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 backdrop-blur-xl">

      <div className="text-slate-500 text-xs mb-2 uppercase tracking-wide">

        {title}

      </div>

      <div className="text-2xl font-bold text-white">

        {value}

      </div>

    </div>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
}) {

  return (

    <div className="flex items-center justify-between">

      <div className="flex items-center gap-2 text-slate-400">

        <Icon size={15} />

        <span>{label}</span>

      </div>

      <span className="text-white font-medium">

        {value}

      </span>

    </div>
  );
}