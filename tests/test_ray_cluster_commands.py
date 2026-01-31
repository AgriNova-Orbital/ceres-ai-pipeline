from modules.wheat_risk.ray_cluster import (
    RayHeadConfig,
    RayWorkerConfig,
    build_ray_head_command,
    build_ray_worker_command,
)


def test_build_ray_head_command_defaults():
    cmd = build_ray_head_command(RayHeadConfig())
    assert cmd[:3] == ["ray", "start", "--head"]
    assert "--port=6379" in cmd
    assert "--dashboard-host=0.0.0.0" in cmd


def test_build_ray_worker_command_defaults():
    cmd = build_ray_worker_command(RayWorkerConfig(head_address="100.1.2.3:6379"))
    assert cmd[:2] == ["ray", "start"]
    assert "--address=100.1.2.3:6379" in cmd
    assert "--num-gpus=1" in cmd
