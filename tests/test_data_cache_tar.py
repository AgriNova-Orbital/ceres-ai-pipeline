import tarfile
import tempfile
from pathlib import Path


def _make_tar_with_index(tmp: Path) -> tuple[Path, str]:
    ds = tmp / "stage1"
    (ds / "shards").mkdir(parents=True)
    (ds / "index.csv").write_text("npz_path\nshards/a.npz\n")
    (ds / "shards" / "a.npz").write_bytes(b"\x93NUMPY")

    tar_path = tmp / "stage1.tar"
    with tarfile.open(tar_path, mode="w") as tar:
        tar.add(ds, arcname="stage1")
    return tar_path, "stage1"


def test_ensure_dataset_cached_from_file_url_tar():
    from modules.wheat_risk.data_cache import ensure_dataset_cached

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        tar_path, root_name = _make_tar_with_index(tmp)
        url = tar_path.as_uri()

        cache_root = tmp / "cache"
        ds_dir = ensure_dataset_cached(
            data_url=url,
            dataset_name=root_name,
            cache_root=cache_root,
            expected_index_relpath="index.csv",
        )

        assert (ds_dir / "index.csv").exists()
        assert (ds_dir / "shards" / "a.npz").exists()
        assert (ds_dir / ".ready").exists()


def test_extract_blocks_path_traversal():
    # If zstandard isn't installed, skip this test.
    try:
        import zstandard  # noqa: F401
    except Exception:
        return

    from modules.wheat_risk.data_cache import extract_tar_zst

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bad_tar = tmp / "bad.tar"
        with tarfile.open(bad_tar, mode="w") as tar:
            f = tmp / "x.txt"
            f.write_text("x")
            tar.add(f, arcname="../escape.txt")

        # Wrap bad tar into zst
        import zstandard as zstd

        zst_path = tmp / "bad.tar.zst"
        cctx = zstd.ZstdCompressor(level=1)
        with bad_tar.open("rb") as src, zst_path.open("wb") as dst:
            with cctx.stream_writer(dst) as w:
                w.write(src.read())

        out_dir = tmp / "out"
        try:
            extract_tar_zst(zst_path, out_dir)
        except RuntimeError as e:
            assert "Unsafe path" in str(e)
        else:
            raise AssertionError("expected RuntimeError")
