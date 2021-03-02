import numpy as np
import os


def create_cube_mesh(file_name, centre_point, side_len, description=None, verbose=False):

    mesh_dir = os.path.dirname(file_name)
    if len(mesh_dir) > 0 and not os.path.exists(mesh_dir):
        os.makedirs(mesh_dir)

    if type(centre_point) is not np.ndarray:
        centre_point = np.array(centre_point)

    if verbose:
        print("Creating cube mesh")
        print("File: " + str(file_name))
        print("Centre: " + str(centre_point))
        print("Side: " + str(side_len))
        print("Description: " + str(description))

    vertex = np.array([[0.0, 0.0, 0.0],
                       [0.0, 0.0, 1.0],
                       [0.0, 1.0, 0.0],
                       [0.0, 1.0, 1.0],
                       [1.0, 0.0, 0.0],
                       [1.0, 0.0, 1.0],
                       [1.0, 1.0, 0.0],
                       [1.0, 1.0, 1.0]])

    # Centre cube
    vertex -= np.array([0.5, 0.5, 0.5])

    # Scale the cube to right size
    vertex *= side_len

    # Position cube

    vertex += centre_point

    vertex *= 1e6  # The other obj files are in micrometers, so convert :(

    normal_str = "vn  0.0  0.0  1.0\n" \
                 + "vn  0.0  0.0 -1.0\n" \
                 + "vn  0.0  1.0  0.0\n" \
                 + "vn  0.0 -1.0  0.0\n" \
                 + "vn  1.0  0.0  0.0\n" \
                 + "vn -1.0  0.0  0.0\n"

    face_str = "f  1//2  7//2  5//2\n" \
               + "f  1//2  3//2  7//2\n" \
               + "f  1//6  4//6  3//6\n" \
               + "f  1//6  2//6  4//6\n" \
               + "f  3//3  8//3  7//3\n" \
               + "f  3//3  4//3  8//3\n" \
               + "f  5//5  7//5  8//5\n" \
               + "f  5//5  8//5  6//5\n" \
               + "f  1//4  5//4  6//4\n" \
               + "f  1//4  6//4  2//4\n" \
               + "f  2//1  6//1  8//1\n" \
               + "f  2//1  8//1  4//1\n"

    with open(file_name, 'wt') as f:
        f.write("# Generated by create_cube_mesh.py\n")
        f.write(f"# {description}\n\n")

        f.write("g cube\n\n")

        for row in vertex:
            f.write("v %f %f %f\n" % tuple(row))

        f.write(f"\n{normal_str}")

        f.write(f"\n{face_str}")


if __name__ == "__main__":
    create_cube_mesh(file_name="test-cube.obj",
                     centre_point=[1, 2, 3],
                     side_len=2,
                     description="This is a test cube")
