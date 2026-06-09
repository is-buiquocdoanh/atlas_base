# atlas_base

ROS 2 (Humble) monorepo chứa 4 package lõi cho robot AMR Atlas. Thiết kế để dùng làm **git submodule** trong bất kỳ dự án robot nào.

## Cấu trúc

```
atlas_base/
├── atlas_api/      # REST + WebSocket API server (Flask + rclpy)
├── atlas_map/      # Dữ liệu bản đồ (YAML + PGM + posegraph)
├── atlas_slam/     # Launch files + config cho SLAM & Navigation (Nav2)
└── atlas_web/      # Web dashboard (Flask, port 8888)
```

## Yêu cầu

- ROS 2 Humble
- Nav2 (`ros-humble-navigation2`)
- slam_toolbox (`ros-humble-slam-toolbox`)
- Python packages: `flask`, `flask-sock`, `rclpy`

## Thêm vào dự án mới

```bash
# 1. Trong workspace mới
cd ~/your_robot_ws/src
git submodule add git@github.com:is-buiquocdoanh/atlas_base.git atlas_base

# 2. Build
cd ..
colcon build

# 3. Khi clone lại dự án (luôn thêm --recurse-submodules)
git clone --recurse-submodules git@github.com:is-buiquocdoanh/your_robot_ws.git
```

## Khởi chạy

### API Server

```bash
# Robot thật
ros2 launch atlas_api atlas_api_real.launch.py

# Simulation
ros2 launch atlas_api atlas_api_sim.launch.py
```

Web dashboard tự động mở tại `http://<robot_ip>:8888`

### SLAM (tạo bản đồ mới)

```bash
# Robot thật
ros2 launch atlas_slam atlas_slam_toolbox_real.launch.py

# Simulation
ros2 launch atlas_slam atlas_slam_toolbox_sim.launch.py

# Với bản đồ có sẵn (incremental mapping)
ros2 launch atlas_slam atlas_slam_toolbox_real.launch.py \
  map_file:=/path/to/maps/my_map
```

### Map Server (định vị với bản đồ đã lưu)

```bash
ros2 launch atlas_slam atlas_map_server_real.launch.py \
  map:=/path/to/maps/my_map/my_map.yaml
```

### Navigation (Nav2)

```bash
ros2 launch atlas_slam atlas_navigation_real.launch.py
```

### Cartographer (thay thế slam_toolbox)

```bash
ros2 launch atlas_slam atlas_cartographer_real.launch.py
```

## Bản đồ

Bản đồ lưu tại `atlas_map/<tên_map>/` gồm các file:

| File | Mô tả |
|------|-------|
| `.yaml` | Metadata (origin, resolution, …) |
| `.pgm` | Ảnh occupancy grid |
| `.posegraph` | Posegraph của slam_toolbox (để incremental mapping) |
| `.data` | Data đi kèm posegraph |

Bản đồ mặc định: `atlas_map/ware_house/warehouse.yaml`

## Cập nhật atlas_base

```bash
cd src/atlas_base
# ... sửa code ...
git add . && git commit -m "mô tả thay đổi" && git push

# Cập nhật pointer trong dự án chính
cd ../..
git add src/atlas_base && git commit -m "update atlas_base"
```

## Kéo cập nhật mới nhất từ atlas_base

```bash
git submodule update --remote src/atlas_base
git add src/atlas_base && git commit -m "bump atlas_base"
```
