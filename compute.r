lcm.compute <- function(AVP, OC = 1, IC = 1, cut = 300) {
  
  N = length(AVP)+2*IC+OC-1
  
  # Vecteurs de travail
  t = rep(0.0, N)
  print(AVP)
  print(IC+OC)
  t[(IC+OC):(IC+OC+length(AVP)-1)] = AVP
  print(t)
  v = t-cut

  print(v)
  SV  = rep(0.0, N)
  SV1 = SV
  SV2 = SV
  SO  = SV
  SO1 = SV
  SO2 = SV

  SVP = rep(0, N)
  SOP = rep(0, N)
  
  # Initialisation
  for (i in OC:(IC+OC-1)) {SV[i] = sum(v[(i-OC+1):(i)])}
  SVP[IC+OC-1]=IC
  SOP[IC+OC-1]=1
  
  print(SV)

  # Calcul des valeurs
  for (i in (IC+OC):N){
    print(i)
    # Calcul de SV
    SV1[i] = SV[i-1]+v[i]
    SV2[i] = SO[i-OC]+sum(v[(i-OC+1):(i)])
    SV[i]  = max(SV1[i], SV2[i])
    print(c(SV[i-1], v[i], SV1[i], SO[i-OC], SV2[i], SV[i]))
    # Calcul de SO
    SO1[i] = SO[i-1]
    SO2[i] = SV[i-IC]
    SO[i]  = max(SO1[i], SO2[i])

    print(c(SO1[i], SO2[i], SO[i]))
    
    # Limites de chantiers
    if( SV1[i] >= SV2[i]) { SVP[i] = SVP[i-1]}
    else {SVP[i] = i - OC + 1}
    
    if( SO1[i] >  SO2[i]) { SOP[i] = SOP[i-1]}
    else {SOP[i] = i - IC + 1}
    
  }
  print(SOP)
  print(SVP)
  
  # Calcul des chantiers
  int.nbr.max = 2*ceiling(N/(OC+IC))
  
  int.from  = rep(0, int.nbr.max)
  int.to    = rep(0, int.nbr.max)
  int.code  = rep(0, int.nbr.max)
  int.accu  = rep(0, int.nbr.max)

  int.nbr = 0
  int.idx = N
  while(SOP[int.idx] > 1){
    
    # L'intercalaire
    int.nbr = int.nbr+1
    int.to[int.nbr] = int.idx
    int.from[int.nbr] = SOP[int.to[int.nbr]]
    int.code[int.nbr] = 0
    int.accu[int.nbr] = 0.0
    print ("---------------------------")
    print (c(int.nbr, int.from[int.nbr]))

    # Le chantier
    int.nbr = int.nbr+1
    int.to[int.nbr] = int.from[int.nbr-1]-1
    int.from[int.nbr] = SVP[int.to[int.nbr]]
    int.code[int.nbr] = 1
    int.accu[int.nbr] = sum(cut+v[int.from[int.nbr]:int.to[int.nbr]])
    print (c(int.nbr, int.from[int.nbr]))
    
    # mise à jour l'index
    int.idx = int.from[int.nbr]-1
    print(int.idx)
    }
  
  ff = rev(int.from[1:int.nbr])-(OC+IC-1)
  ff[1] = max(ff[1],1)
  tt = rev(int.to[1:int.nbr])-(OC+IC-1)
  cc = rev(int.code[1:int.nbr])
  aa = rev(int.accu[1:int.nbr])

  print(int.code)
  print(int.from)
  print(int.to)
  print(int.accu)
  print(int.code)

  print(ff)
  print(tt)
  print(cc)
  print(AVP)
  
  return(list(from = ff, to = tt, code = cc, accu = aa
  ))
}

lcm.compute(c(0,0,0,0,3,3,3,1,0,2,4,0,2,0,0), 2, 3, 1)

