import folium

m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)

layer1 = folium.FeatureGroup(name="테스트 레이어 1", overlay=True, show=True)
folium.Circle([37.57, 126.98], radius=500, color="red").add_to(layer1)
layer1.add_to(m)

layer2 = folium.FeatureGroup(name="테스트 레이어 2", overlay=True, show=False)
folium.Circle([37.56, 126.99], radius=500, color="blue").add_to(layer2)
layer2.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

print("Layers attached:", [child.layer_name for child in m._children.values() if hasattr(child, "layer_name")])
m.save("index.html")
print("[OK] Open index.html")