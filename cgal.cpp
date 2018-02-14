// c++ -shared cgal.cpp -lCGAL -lgmp -I/usr/include/python3.5m/ -lboost_python-py35 -fPIC -o cgal.so
//
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Constrained_Delaunay_triangulation_2.h>
#include <CGAL/Triangulation_face_base_with_info_2.h>
#include <CGAL/Polygon_2.h>
#include <iostream>
#include <Python.h>
#include <string>
#include <boost/python.hpp>

#include <CGAL/Simple_cartesian.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/corefinement.h>

namespace delaunay
{
struct FaceInfo2
{
  FaceInfo2(){}
  int nesting_level;
  bool in_domain(){ 
    return nesting_level%2 == 1;
  }
};

typedef CGAL::Exact_predicates_inexact_constructions_kernel       K;
typedef CGAL::Triangulation_vertex_base_2<K>                      Vb;
typedef CGAL::Triangulation_face_base_with_info_2<FaceInfo2,K>    Fbb;
typedef CGAL::Constrained_triangulation_face_base_2<K,Fbb>        Fb;
typedef CGAL::Triangulation_data_structure_2<Vb,Fb>               TDS;
typedef CGAL::Exact_predicates_tag                                Itag;
typedef CGAL::Constrained_Delaunay_triangulation_2<K, TDS, Itag>  CDT;
typedef CDT::Point                                                Point;
typedef CGAL::Polygon_2<K>                                        Polygon_2;
void 
mark_domains(CDT& ct, 
             CDT::Face_handle start, 
             int index, 
             std::list<CDT::Edge>& border )
{
  if(start->info().nesting_level != -1){
    return;
  }
  std::list<CDT::Face_handle> queue;
  queue.push_back(start);
  while(! queue.empty()){
    CDT::Face_handle fh = queue.front();
    queue.pop_front();
    if(fh->info().nesting_level == -1){
      fh->info().nesting_level = index;
      for(int i = 0; i < 3; i++){
        CDT::Edge e(fh,i);
        CDT::Face_handle n = fh->neighbor(i);
        if(n->info().nesting_level == -1){
          if(ct.is_constrained(e)) border.push_back(e);
          else queue.push_back(n);
        }
      }
    }
  }
}
//explore set of facets connected with non constrained edges,
//and attribute to each such set a nesting level.
//We start from facets incident to the infinite vertex, with a nesting
//level of 0. Then we recursively consider the non-explored facets incident 
//to constrained edges bounding the former set and increase the nesting level by 1.
//Facets in the domain are those with an odd nesting level.
void
mark_domains(CDT& cdt)
{
  for(CDT::All_faces_iterator it = cdt.all_faces_begin(); it != cdt.all_faces_end(); ++it){
    it->info().nesting_level = -1;
  }
  std::list<CDT::Edge> border;
  mark_domains(cdt, cdt.infinite_face(), 0, border);
  while(! border.empty()){
    CDT::Edge e = border.front();
    border.pop_front();
    CDT::Face_handle n = e.first->neighbor(e.second);
    if(n->info().nesting_level == -1){
      mark_domains(cdt, n, e.first->info().nesting_level+1, border);
    }
  }
}

template<typename python_iterable>
boost::python::list delaunay(const python_iterable &polygon)
{
    Polygon_2 poly;
    for (int i=0; i<len(polygon); i++)
    {
      poly.push_back(Point(
          boost::python::extract<double>(polygon[i][0]),
          boost::python::extract<double>(polygon[i][1])));
    }

    CDT cdt;
    cdt.insert_constraint(poly.vertices_begin(), poly.vertices_end(), true);

    mark_domains(cdt);

    boost::python::list list;
    int count=0;
    for (CDT::Finite_faces_iterator fit=cdt.finite_faces_begin();
                                    fit!=cdt.finite_faces_end();++fit)
    {
        if (fit->info().in_domain())
        {
            list.append(boost::python::make_tuple(
                boost::python::make_tuple(fit->vertex(0)->point().x(), fit->vertex(0)->point().y()),
                boost::python::make_tuple(fit->vertex(1)->point().x(), fit->vertex(1)->point().y()),
                boost::python::make_tuple(fit->vertex(2)->point().x(), fit->vertex(2)->point().y())));
      }
    }

    return list;
}
}

namespace boolean 
{
typedef CGAL::Simple_cartesian<double> K;
typedef K::Point_3 Point;
typedef CGAL::Surface_mesh<Point> Mesh;
namespace PMP = CGAL::Polygon_mesh_processing;

Mesh create_mesh(const boost::python::list &vtx, const boost::python::list &idx)
{
    Mesh out;
    std::vector<Mesh::Vertex_index> vtx_idx; 
    for (int i=0; i<len(vtx); i++)
    {
        vtx_idx.push_back(out.add_vertex(Point(
            boost::python::extract<double>(vtx[i][0]),
            boost::python::extract<double>(vtx[i][1]),
            boost::python::extract<double>(vtx[i][2]))));
    }

    for (int i=0; i<len(idx); i++)
    {
          const int a = boost::python::extract<int>(idx[i][0]);
          const int b = boost::python::extract<int>(idx[i][1]);
          const int c = boost::python::extract<int>(idx[i][2]);
          std::cout << a << " " << b << " " << c << "\n";
          out.add_face(vtx_idx[a], vtx_idx[b], vtx_idx[c]);
    }
    return out;
}

Mesh union_(Mesh &a, Mesh &b)
{
    Mesh out;
    const bool valid_union = PMP::corefine_and_compute_union(a, b, out);
    if (!valid_union)
        throw std::runtime_error("union could not be computed");
    return out;
}

}

void translator(std::exception const& e) {
    PyErr_SetString(PyExc_UserWarning, e.what());
}

BOOST_PYTHON_MODULE(cgal)
{
    using namespace boost::python;
    def("delaunay", delaunay::delaunay<boost::python::list>);
    def("delaunay", delaunay::delaunay<boost::python::tuple>);
    class_<boolean::Mesh>("Mesh", init<>())
        .add_property("number_of_vertices", &boolean::Mesh::number_of_vertices)
        .add_property("number_of_faces", &boolean::Mesh::number_of_faces);
    def("union", boolean::union_);
    def("create_mesh", boolean::create_mesh);
    register_exception_translator<std::exception>(translator);
}


